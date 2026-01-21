from __future__ import annotations

import json
from typing import List

from crewai import Agent, Task

from backend.schemas import NewsResearchResult, Source
from backend.tools.serper_search import serper_search


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


def _serper_tool(company_name: str, keywords: List[str]) -> List[Source]:
    # Multiple focused queries yields better coverage; Manager can trigger a second pass if needed.
    queries = [
        f"{company_name} company overview headquarters CEO founded employees",
        f"{company_name} product launch pricing plans",
        f"{company_name} partnership acquisition layoff reorg press release",
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


def build_news_task(
    agent: Agent,
    *,
    competitor_name: str,
    keywords: List[str],
) -> Task:
    sources = _serper_tool(competitor_name, keywords)
    sources_payload = [s.model_dump() for s in sources]

    prompt = f"""
You are the NewsResearcher.

Using ONLY the sources list below (Serper search results), extract structured information.

Return ONLY valid JSON that matches this schema:
{NewsResearchResult.model_json_schema()}

Rules:
- Return JSON ONLY (no markdown, no backticks, no trailing commentary).
- Prefer last 6-12 months for Recent Developments.
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
