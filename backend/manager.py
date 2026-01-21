from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import List, Literal, Optional

from crewai import Agent, Crew, Process, Task

from backend.financial_analyst import build_financial_analyst_agent, build_financial_task
from backend.news_researcher import build_news_researcher_agent, build_news_task
from backend.report_writer import build_report_task, build_report_writer_agent
from backend.schemas import ManagerParsedPrompt, ManagerState, NewsResearchResult, SimpleFactResult

logger = logging.getLogger(__name__)


def _parse_prompt_with_llm(prompt: str, llm) -> Optional[ManagerParsedPrompt]:
    """Use the LLM to extract a structured ManagerParsedPrompt from free-form text.

    We still validate with Pydantic and fall back to deterministic regex parsing if it fails.
    """

    # We avoid Crew/Agent here intentionally to keep parsing fast and deterministic.
    instruction = (
        "Extract structured fields from the user prompt for a competitor research report. "
        "Return ONLY valid JSON that matches the schema exactly. "
        "If a field is unknown, use null (for optional strings) or [] for keywords. "
        "Do not wrap in markdown/backticks. Do not include extra keys."
    )

    schema = ManagerParsedPrompt.model_json_schema()

    messages = [
        {"role": "system", "content": instruction},
        {
            "role": "user",
            "content": (
                "USER PROMPT:\n"
                + prompt
                + "\n\nJSON SCHEMA:\n"
                + json.dumps(schema)
            ),
        },
    ]

    try:
        # CrewAI LLM exposes a call interface; we keep this best-effort and tolerant.
        raw = llm.call(messages)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("LLM prompt parsing failed")
        return None

    if not isinstance(raw, str) or not raw.strip():
        return None

    try:
        return ManagerParsedPrompt.model_validate_json(raw)
    except Exception:
        logger.warning("LLM output did not validate as ManagerParsedPrompt. raw=%r", raw)
        return None


@dataclass
class ManagerResult:
    state: ManagerState
    memo_markdown: str


def build_manager_agent(llm) -> Agent:
    return Agent(
        role="Manager",
        goal="Orchestrate the research + analysis workflow and ensure structured, complete output.",
        backstory=(
            "You are an operations-focused research manager. You decompose prompts into steps, "
            "validate completeness, and ensure each specialist agent produces structured outputs." 
        ),
        llm=llm,
        verbose=False,
        allow_delegation=True,
    )


def _parse_prompt_with_regex(prompt: str) -> ManagerParsedPrompt:
    # Minimal deterministic parsing; LLM parsing is preferred, regex is fallback.
    competitor = None
    ticker = None

    m = re.search(r"competitor\s*:\s*([^\n\.\,]+)", prompt, flags=re.IGNORECASE)
    if m:
        competitor = m.group(1).strip()

    m2 = re.search(r"ticker\s*:\s*([A-Za-z\.\-]{1,8})", prompt, flags=re.IGNORECASE)
    if m2:
        ticker = m2.group(1).strip().upper()

    if not competitor:
        # fallback: first line chunk
        competitor = prompt.strip().split("\n")[0][:80].strip()

    # Keywords: drop stopwords-ish, keep nouns-ish tokens
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-\+]{2,}", prompt)
    stop = {
        "find",
        "latest",
        "news",
        "press",
        "releases",
        "product",
        "products",
        "launch",
        "launches",
        "for",
        "about",
        "research",
        "competitor",
        "focus",
        "recent",
        "pricing",
        "and",
        "any",
        "financial",
        "signals",
    }
    keywords = []
    for t in tokens:
        tl = t.lower()
        if tl in stop:
            continue
        if tl == competitor.lower():
            continue
        keywords.append(t)

    # de-dup preserve order
    seen = set()
    keywords2: List[str] = []
    for k in keywords:
        if k.lower() in seen:
            continue
        seen.add(k.lower())
        keywords2.append(k)

    return ManagerParsedPrompt(
        competitor_name=competitor,
        ticker=ticker,
        keywords=keywords2[:10],
    )


def _needs_second_search(nr: NewsResearchResult) -> bool:
    co = nr.company_overview
    # Critical fields: description + at least one exec or HQ or founded
    missing = 0
    if not co.description or co.description.strip().lower() in {"unknown", "n/a"}:
        missing += 1
    if co.founded.strip().lower() == "unknown":
        missing += 1
    if co.hq_location.strip().lower() == "unknown":
        missing += 1
    if not co.executives:
        missing += 1
    return missing >= 3


IntentType = Literal["simple_fact", "full_report"]


_SIMPLE_FACT_PATTERNS = [
    # Accept optional trailing '?' so "Who is the CEO of Tesla" routes correctly.
    r"^\s*who\s+is\s+the\s+ceo\s+of\s+.+\??\s*$",
    r"^\s*who\s+is\s+.+\??\s*$",
    r"^\s*where\s+is\s+.+\s+(headquartered|based)\??\s*$",
    r"^\s*when\s+was\s+.+\s+founded\??\s*$",
    r"^\s*what\s+is\s+.+\s+ticker\??\s*$",
    r"^\s*how\s+many\s+employees\s+does\s+.+\s+have\??\s*$",
    r"^\s*what\s+does\s+.+\s+do\??\s*$",
]

_FULL_REPORT_KEYWORDS = [
    "research",
    "competitor",
    "analysis",
    "analyze",
    "market report",
    "swot",
    "pricing analysis",
    "write a memo",
    "memo",
    "report",
]


def detect_intent(user_message: str) -> IntentType:
    msg = (user_message or "").strip().lower()
    for kw in _FULL_REPORT_KEYWORDS:
        if kw in msg:
            return "full_report"

    # If it mentions ticker with a verb like research/analyze handled above.
    for pat in _SIMPLE_FACT_PATTERNS:
        if re.match(pat, msg, flags=re.IGNORECASE):
            return "simple_fact"

    # Heuristic: short length + contains facty terms (punctuation optional).
    fact_terms = ["ceo", "founder", "headquartered", "headquarters", "ticker", "employees", "founded"]
    if len(msg) <= 120 and any(t in msg for t in fact_terms):
        # Avoid routing imperative prompts without a question mark unless they clearly look like a question.
        if "?" in msg or msg.startswith(("who ", "where ", "when ", "what ", "how many ")):
            return "simple_fact"

    return "full_report"


def _extract_entity_from_question(user_message: str) -> str:
    # Very lightweight extraction for simple Qs.
    msg = (user_message or "").strip()
    patterns = [
        r"ceo of\s+(?P<e>.+)\?",
        r"where is\s+(?P<e>.+)\s+(headquartered|based)\?",
        r"when was\s+(?P<e>.+)\s+founded\?",
        r"what is\s+(?P<e>.+)\s+ticker\?",
        r"how many employees does\s+(?P<e>.+)\s+have\?",
        r"what does\s+(?P<e>.+)\s+do\?",
    ]
    for p in patterns:
        m = re.search(p, msg, flags=re.IGNORECASE)
        if m:
            ent = m.group("e").strip()
            ent = re.sub(r"[\?\.]+$", "", ent).strip()
            return ent

    # fallback: remove leading question words
    ent = re.sub(r"^(who|where|when|what|how many)\b", "", msg, flags=re.IGNORECASE).strip()
    return re.sub(r"[\?\.]+$", "", ent).strip()[:80]


def _focused_query_for_simple_fact(question: str, entity: str) -> str:
    q = question.lower()
    if "ceo" in q:
        return f"{entity} CEO"
    if "headquartered" in q or "headquarters" in q or "based" in q:
        return f"{entity} headquarters"
    if "founded" in q:
        return f"{entity} founded year"
    if "ticker" in q:
        return f"{entity} ticker symbol"
    if "employees" in q or "headcount" in q:
        return f"{entity} number of employees"
    if "what does" in q and "do" in q:
        return f"what does {entity} do"
    return f"{entity} {question}".strip()


def _run_simple_fact(*, user_message: str, llm) -> str:
    entity = _extract_entity_from_question(user_message)
    focused_query = _focused_query_for_simple_fact(user_message, entity)
    logger.info(
        "Intent routing: simple_fact entity=%r focused_query=%r",
        entity,
        focused_query,
    )

    news_agent = build_news_researcher_agent(llm)
    news_task = build_news_task(
        news_agent,
        competitor_name=entity or "unknown",
        keywords=[],
        mode="simple_fact",
        question=user_message,
        focused_query=focused_query,
    )

    crew = Crew(
        agents=[news_agent],
        tasks=[news_task],
        process=Process.sequential,
        verbose=bool(os.getenv("CREW_VERBOSE")),
    )
    _ = crew.kickoff()

    sf = news_task.output.pydantic  # type: ignore[assignment]
    if sf is None:
        logger.error(
            "SimpleFact task produced no parsed output. raw=%r",
            getattr(news_task.output, "raw", None),
        )
        raw = getattr(news_task.output, "raw", None)
        if isinstance(raw, str):
            sf = SimpleFactResult.model_validate_json(raw)
        else:
            raise RuntimeError("SimpleFactResult parsing failed")

    logger.info(
        "Intent routing: simple_fact source_url=%r confidence=%r",
        sf.source_url,
        sf.confidence,
    )

    # Return one sentence, optionally append citation if it still stays one sentence.
    answer = sf.answer.strip()
    answer = re.sub(r"\s+", " ", answer)
    answer = re.sub(r"^[-*•]\s+", "", answer)
    # Ensure single sentence by truncation.
    m = re.search(r"[\.!?]", answer)
    if m:
        answer = answer[: m.end()].strip()
    else:
        answer = answer.rstrip(".") + "."

    # Append citation in parentheses if it doesn't create an extra sentence.
    if sf.source_url and sf.source_url not in answer:
        answer = answer.rstrip(".") + f" ({sf.source_url})."
    return answer


def run_manager_workflow(*, competitor_prompt: str, llm) -> ManagerResult:
    intent = detect_intent(competitor_prompt)
    logger.info("Detected intent=%s", intent)

    if intent == "simple_fact":
        direct = _run_simple_fact(user_message=competitor_prompt, llm=llm)
        # Keep API contract consistent: return via memo_markdown.
        state = ManagerState(
            competitor_name=_extract_entity_from_question(competitor_prompt) or "unknown",
            parsed_prompt=ManagerParsedPrompt(competitor_name="unknown"),
        )
        return ManagerResult(state=state, memo_markdown=direct)

    parsed = _parse_prompt_with_llm(competitor_prompt, llm) or _parse_prompt_with_regex(
        competitor_prompt
    )
    logger.info("Parsed prompt: %s", parsed.model_dump())

    state = ManagerState(competitor_name=parsed.competitor_name, parsed_prompt=parsed)

    # Build specialist agents
    news_agent = build_news_researcher_agent(llm)
    fin_agent = build_financial_analyst_agent(llm)
    writer_agent = build_report_writer_agent(llm)

    logger.info("Invoking agents: NewsResearcher -> FinancialAnalyst -> ReportWriter")

    # 1) News research
    news_task = build_news_task(
        news_agent,
        competitor_name=parsed.competitor_name,
        keywords=parsed.keywords,
        mode="report_research",
    )

    crew = Crew(
        agents=[news_agent],
        tasks=[news_task],
        process=Process.sequential,
        verbose=bool(os.getenv("CREW_VERBOSE")),
    )
    _ = crew.kickoff()

    # Validate LLM/tool output before dereferencing.
    nr = news_task.output.pydantic  # type: ignore[assignment]
    if nr is None:
        # This happens when the agent fails to produce valid JSON that matches
        # [`NewsResearchResult`](backend/schemas.py:38) (e.g. truncated / non-JSON / schema mismatch).
        # Log raw output to diagnose instead of crashing with AttributeError.
        logger.error(
            "NewsResearch task produced no parsed output. raw=%r",
            getattr(news_task.output, "raw", None),
        )
        # Best-effort fallback: if raw output is valid JSON, parse it ourselves.
        raw = getattr(news_task.output, "raw", None)
        if isinstance(raw, str):
            try:
                nr = NewsResearchResult.model_validate_json(raw)
                logger.warning(
                    "Recovered NewsResearchResult by parsing raw JSON output directly."
                )
            except Exception as e:
                raise RuntimeError(
                    "NewsResearchResult parsing failed (task.output.pydantic is None). "
                    "Raw output could not be validated against schema."
                ) from e
        else:
            raise RuntimeError(
                "NewsResearchResult parsing failed (task.output.pydantic is None). "
                "Enable CREW_VERBOSE=1 to inspect agent output."
            )

    if _needs_second_search(nr):
        logger.warning("News results incomplete; running targeted second search")
        second_keywords = parsed.keywords + ["CEO", "headcount", "headquarters", "founded"]
        news_task2 = build_news_task(
            news_agent,
            competitor_name=parsed.competitor_name,
            keywords=second_keywords,
        )
        crew2 = Crew(
            agents=[news_agent],
            tasks=[news_task2],
            process=Process.sequential,
            verbose=bool(os.getenv("CREW_VERBOSE")),
        )
        _ = crew2.kickoff()
        nr = news_task2.output.pydantic  # type: ignore[assignment]

    state.company_overview = nr.company_overview
    state.recent_developments = nr.recent_developments
    state.products_pricing = nr.products_pricing
    state.sources.extend(nr.sources)

    # 2) Financial analysis
    fin_task = build_financial_task(
        fin_agent,
        competitor_name=parsed.competitor_name,
        ticker=parsed.ticker,
    )
    crew3 = Crew(
        agents=[fin_agent],
        tasks=[fin_task],
        process=Process.sequential,
        verbose=bool(os.getenv("CREW_VERBOSE")),
    )
    _ = crew3.kickoff()

    fa = fin_task.output.pydantic  # type: ignore[assignment]
    if fa is None:
        logger.error(
            "FinancialAnalysis task produced no parsed output. raw=%r",
            getattr(fin_task.output, "raw", None),
        )
        raw = getattr(fin_task.output, "raw", None)
        if isinstance(raw, str):
            try:
                from backend.schemas import FinancialAnalysisResult

                fa = FinancialAnalysisResult.model_validate_json(raw)
                logger.warning(
                    "Recovered FinancialAnalysisResult by parsing raw JSON output directly."
                )
            except Exception as e:
                raise RuntimeError(
                    "FinancialAnalysisResult parsing failed (task.output.pydantic is None)."
                ) from e
        else:
            raise RuntimeError(
                "FinancialAnalysisResult parsing failed (task.output.pydantic is None)."
            )

    state.financial_overview = fa.financial_overview
    state.sources.extend(fa.sources)

    # 3) Report writing
    report_task = build_report_task(writer_agent, state=state)
    crew4 = Crew(
        agents=[writer_agent],
        tasks=[report_task],
        process=Process.sequential,
        verbose=bool(os.getenv("CREW_VERBOSE")),
    )
    _ = crew4.kickoff()

    report = report_task.output.pydantic  # type: ignore[assignment]
    if report is None:
        logger.error(
            "Report task produced no parsed output. raw=%r",
            getattr(report_task.output, "raw", None),
        )
        raw = getattr(report_task.output, "raw", None)
        if isinstance(raw, str):
            try:
                from backend.schemas import ReportMemo

                report = ReportMemo.model_validate_json(raw)
                logger.warning("Recovered ReportMemo by parsing raw JSON output directly.")
            except Exception as e:
                raise RuntimeError(
                    "ReportMemo parsing failed (task.output.pydantic is None)."
                ) from e
        else:
            raise RuntimeError("ReportMemo parsing failed (task.output.pydantic is None).")

    memo = report.render_markdown()
    return ManagerResult(state=state, memo_markdown=memo)
