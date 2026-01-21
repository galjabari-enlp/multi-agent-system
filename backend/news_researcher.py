from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from crewai import Agent, Task

from backend.schemas import NewsResearchOutput, NewsResearchResult, QuickAnswerResult, Source
from backend.tools.serper_search import serper_search

logger = logging.getLogger(__name__)


def build_news_researcher_agent(llm) -> Agent:
    return Agent(
        role="NewsResearcher",
        goal="Find recent news, product updates, partnerships, and core company facts with citations.",
        backstory=(
            "You are an investigative market researcher. You use Serper web search results "
            "and extract structured, factual findings with explicit unknowns." 
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def _serper_report_sources(company_name: str, keywords: List[str]) -> List[Source]:
    # Multiple focused queries yields better coverage; Manager can trigger a second pass if needed.
    # Include dedicated queries for HQ + leadership + headcount to reduce "unknown" fields.
    queries = [
        f"{company_name} headquarters location corporate HQ",
        f"{company_name} CEO leadership executives founders",
        f"{company_name} employee count headcount employees",
        f"{company_name} company overview founded",
        f"{company_name} product launch pricing plans",
        f"{company_name} partnership acquisition layoff reorg press release",
        f"{company_name} press release newsroom",
        f"{company_name} news 2024 2025",
    ]
    if keywords:
        queries.insert(0, f"{company_name} " + " ".join(keywords))

    sources: List[Source] = []
    seen = set()
    for q in queries:
        for s in serper_search(q, num=6):
            if s.url in seen:
                continue
            seen.add(s.url)
            sources.append(s)
    return sources


def _serper_simple_fact_sources(query: str) -> List[Source]:
    # Keep fast: single query, small result set.
    sources = serper_search(query, num=6)
    return sources


def _normalize_one_sentence(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"\s+", " ", s)
    # Remove leading bullets if any
    s = re.sub(r"^[-*•]\s+", "", s)
    # Ensure exactly one sentence-ish: cut after first terminal punctuation.
    m = re.search(r"[\.!?]", s)
    if m:
        s = s[: m.end()].strip()
    else:
        s = s.rstrip(".") + "."
    return s


def _estimate_confidence(answer: str, source_url: str) -> str:
    a = (answer or "").lower()
    if not answer or "couldn't confirm" in a or "cannot confirm" in a or "uncertain" in a:
        return "low"
    if source_url and any(
        d in source_url.lower()
        for d in ["wikipedia.org", "linkedin.com", "reddit.com", "quora.com"]
    ):
        return "medium"
    return "high" if source_url else "low"


def build_news_task(
    agent: Agent,
    *,
    competitor_name: str,
    keywords: List[str],
    mode: str = "report_research",
    question: Optional[str] = None,
    focused_query: Optional[str] = None,
) -> Task:
    if mode == "quick_answer":
        if not focused_query:
            raise ValueError("focused_query is required for quick_answer mode")

        sources = _serper_simple_fact_sources(focused_query)
        sources_payload = [s.model_dump() for s in sources]

        prompt = f"""
You are the NewsResearcher.

Task: Answer a short factual question quickly.

You MUST use ONLY the SOURCES list below (Serper search results). Do NOT fabricate.

Return ONLY valid JSON that matches this schema:
{QuickAnswerResult.model_json_schema()}

Rules:
- mode must be "quick_answer".
- answer must be exactly ONE sentence (no bullet lists, no newlines).
- query_used must be exactly the provided Focused query.
- Pick ONE best source_url from the sources.
- Prefer authoritative sources when possible (official company pages, investor relations, reputable finance sources).
- If results conflict or change frequently (e.g., net worth / market cap), include a time qualifier in the same single sentence if supported by sources.
- If you cannot confirm from reliable sources, answer with ONE sentence indicating uncertainty and still provide the best available source_url.
- Use ONLY double quotes in JSON.

Question: {question or focused_query}
Entity: {competitor_name}
Focused query: {focused_query}

SOURCES:
{json.dumps(sources_payload, indent=2)}
""".strip()

        return Task(
            description=prompt,
            expected_output="JSON matching QuickAnswerResult schema",
            agent=agent,
            output_json=QuickAnswerResult,
        )

    # Default: report_research
    sources = _serper_report_sources(competitor_name, keywords)
    sources_payload = [s.model_dump() for s in sources]

    prompt = f"""
You are the NewsResearcher.

Using ONLY the sources list below (Serper search results), extract structured information.

Return ONLY valid JSON that matches this schema:
{NewsResearchResult.model_json_schema()}

Rules:
- Return JSON ONLY (no markdown, no backticks, no trailing commentary).
- mode must be "report_research".
- Prefer last 6-12 months for Recent Developments.
- For company overview fields (HQ, founded, employees, executives): prefer official pages (about, investor relations) and reputable sources.
- If data is missing, put 'unknown' (string) or [] for lists.
- Use ONLY double quotes in JSON.

Company: {competitor_name}
Keywords/context: {json.dumps(keywords)}

SOURCES:
{json.dumps(sources_payload, indent=2)}
""".strip()

    return Task(
        description=prompt,
        expected_output="JSON matching NewsResearchResult schema",
        agent=agent,
        output_json=NewsResearchResult,
    )
