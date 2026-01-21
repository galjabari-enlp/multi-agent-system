from __future__ import annotations

import json
from typing import Optional

from crewai import Agent, Task

from backend.schemas import ManagerState, ReportMemo


def build_report_writer_agent(llm) -> Agent:
    return Agent(
        role="ReportWriter",
        goal="Synthesize all findings into a concise, factual business memo following the exact template.",
        backstory=(
            "You write investment-grade competitor briefs. You are strict about templates and do not invent facts."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def build_report_task(agent: Agent, *, state: ManagerState) -> Task:
    prompt = f"""
You are the ReportWriter.

You must create a business memo that strictly follows the required template structure and headings.

Return ONLY valid JSON matching this schema:
{ReportMemo.model_json_schema()}

Constraints:
- Be concise, factual, and business-oriented.
- If something is unknown, explicitly say so in the relevant field.
- Use lists for bullet sections.

INPUT STATE:
{json.dumps(state.model_dump(), indent=2)}
""".strip()

    return Task(
        description=prompt,
        expected_output="JSON matching ReportMemo schema",
        agent=agent,
        output_json=ReportMemo,
    )


def render_final_memo(report: ReportMemo) -> str:
    # Enforce exact markdown memo output from the schema renderer.
    return report.render_markdown()
