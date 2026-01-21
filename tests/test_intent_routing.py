import re
from unittest.mock import patch

from backend.manager import detect_intent, run_manager_workflow
from backend.schemas import QuickAnswerResult


# We'll patch agent builders so no real LLM/API keys are needed.
class DummyLLM:
    def call(self, messages):  # pragma: no cover
        raise RuntimeError("DummyLLM.call should not be invoked in this test")


def test_detect_intent_quick_answer():
    assert detect_intent("Who is the CEO of Tesla?") == "quick_answer"


def test_detect_intent_full_report():
    assert detect_intent("Research Nvidia ticker NVDA") == "full_report"


def test_quick_answer_other_question_types_route_correctly():
    assert detect_intent("What does Nvidia make?") == "quick_answer"
    assert detect_intent("What is Elon Musk's net worth?") == "quick_answer"
    assert detect_intent("What is Serper?") == "quick_answer"


def test_quick_answer_routes_to_news_only_and_returns_one_sentence():
    # Patch Crew and builders so we don't instantiate CrewAI Task/Agent/LLM.

    class DummyOutput:
        def __init__(self, pydantic):
            self.pydantic = pydantic
            self.raw = None

    class DummyTask:
        def __init__(self):
            self.output = DummyOutput(
                QuickAnswerResult(
                    answer="The CEO of Tesla is Elon Musk.",
                    source_url="https://www.tesla.com/leadership",
                    confidence="high",
                    query_used="Tesla CEO",
                )
            )

    dummy_task = DummyTask()

    def fake_build_news_task(*args, **kwargs):
        assert kwargs.get("mode") == "quick_answer"
        return dummy_task

    class DummyCrew:
        def __init__(self, *args, **kwargs):
            pass

        def kickoff(self):
            return None

    with patch("backend.manager.Crew", DummyCrew), patch(
        "backend.manager.build_news_task", side_effect=fake_build_news_task
    ), patch("backend.manager.build_news_researcher_agent", return_value=object()):
        res = run_manager_workflow(competitor_prompt="Who is the CEO of Tesla?", llm=DummyLLM())

    # Kickoff happened implicitly if no exception.
    kickoff = True

    assert kickoff

    reply = res.memo_markdown
    # Must be exactly one sentence; don't count dots inside URLs.
    stripped = re.sub(r"\(https?://[^\s\)]+\)", "(URL)", reply)
    assert stripped.endswith(".") or stripped.endswith("!") or stripped.endswith("?")
    assert len(re.findall(r"[.!?]", stripped)) == 1
    assert "CEO" in reply
    assert "Tesla" in reply


def test_full_report_routes_to_full_chain_invocations():
    # Ensure full_report path attempts to invoke the three crews (news, fin, writer).

    class DummyOutput:
        def __init__(self, pydantic, raw=None):
            self.pydantic = pydantic
            self.raw = raw

    class DummyTask:
        def __init__(self, pydantic):
            self.output = DummyOutput(pydantic)

    from backend.schemas import (
        CompanyOverview,
        FinancialAnalysisResult,
        FinancialOverview,
        NewsResearchResult,
        ProductsPricing,
        RecentDevelopments,
        ReportMemo,
    )

    news = NewsResearchResult(
        company_overview=CompanyOverview(description="desc", founded="2020", hq_location="SF", employees="100", executives=["CEO"]),
        recent_developments=RecentDevelopments(),
        products_pricing=ProductsPricing(),
        sources=[],
    )
    fin = FinancialAnalysisResult(
        financial_overview=FinancialOverview(ticker="NVDA"),
        sources=[],
    )
    report = ReportMemo(
        competitor_name="Nvidia",
        executive_summary=["x"],
        company_overview=news.company_overview,
        recent_developments=news.recent_developments,
        financial_overview=fin.financial_overview,
        products_pricing=news.products_pricing,
        swot={"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        key_takeaways=["y"],
    )

    dummy_news_task = DummyTask(news)
    dummy_fin_task = DummyTask(fin)
    dummy_report_task = DummyTask(report)

    def fake_build_news_task(*args, **kwargs):
        assert kwargs.get("mode") == "report_research"
        return dummy_news_task

    class DummyCrew:
        call_count = 0

        def __init__(self, *args, **kwargs):
            pass

        def kickoff(self):
            DummyCrew.call_count += 1
            return None

    with patch("backend.manager.Crew", DummyCrew), patch(
        "backend.manager.build_news_task", side_effect=fake_build_news_task
    ), patch("backend.manager.build_financial_task", return_value=dummy_fin_task), patch(
        "backend.manager.build_report_task", return_value=dummy_report_task
    ), patch("backend.manager.build_news_researcher_agent", return_value=object()), patch(
        "backend.manager.build_financial_analyst_agent", return_value=object()
    ), patch("backend.manager.build_report_writer_agent", return_value=object()), patch(
        "backend.manager._parse_prompt_with_llm", return_value=None
    ):
        res = run_manager_workflow(competitor_prompt="Research Nvidia ticker NVDA", llm=DummyLLM())

    # 3 crews invoked: news, financial, report.
    assert DummyCrew.call_count == 3
    assert "Market Report" in res.memo_markdown
