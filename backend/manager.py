from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import List, Optional

from crewai import Agent, Crew, Process, Task

from backend.financial_analyst import build_financial_analyst_agent, build_financial_task
from backend.news_researcher import build_news_researcher_agent, build_news_task
from backend.report_writer import build_report_task, build_report_writer_agent
from backend.schemas import ManagerParsedPrompt, ManagerState, NewsResearchResult

logger = logging.getLogger(__name__)


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
    # Minimal deterministic parsing; LLM is used for synthesis, not extraction.
    competitor = None
    ticker = None

    m = re.search(r"competitor\s*:\s*([^\n\.\,]+)", prompt, flags=re.IGNORECASE)
    if m:
        competitor = m.group(1).strip()

    m2 = re.search(r"ticker\s*:\s*([A-Za-z\.\-]{1,8})", prompt, flags=re.IGNORECASE)
    if m2:
        ticker = m2.group(1).strip().upper()

    if not competitor:
        # fallback: first capitalized token chunk
        competitor = prompt.strip().split("\n")[0][:80].strip()

    # Keywords: drop stopwords-ish, keep nouns-ish tokens
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-\+]{2,}", prompt)
    stop = {
        "research",
        "competitor",
        "focus",
        "recent",
        "product",
        "products",
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


def run_manager_workflow(*, competitor_prompt: str, llm) -> ManagerResult:
    parsed = _parse_prompt_with_regex(competitor_prompt)
    logger.info("Parsed prompt: %s", parsed.model_dump())

    state = ManagerState(competitor_name=parsed.competitor_name, parsed_prompt=parsed)

    # Build specialist agents
    news_agent = build_news_researcher_agent(llm)
    fin_agent = build_financial_analyst_agent(llm)
    writer_agent = build_report_writer_agent(llm)

    # 1) News research
    news_task = build_news_task(
        news_agent,
        competitor_name=parsed.competitor_name,
        keywords=parsed.keywords,
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
