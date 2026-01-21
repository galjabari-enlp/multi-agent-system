# CrewAI Competitor Market Report (Backend)

Production-ready-ish backend starter for a **CrewAI multi-agent system** that generates a competitor market report.

## What it does
Given a user prompt containing a competitor/company name (optional context), the system:
1. Searches the web via **Serper** for recent news and company facts
2. Pulls market/financial data via **Alpha Vantage** (Python integration)
3. Synthesizes into a structured business memo following the required template

Agents:
- Manager (orchestrator)
- NewsResearcher (Serper)
- FinancialAnalyst (Alpha Vantage)
- ReportWriter (memo)

## Project layout
- [`backend/main.py`](backend/main.py:1) – CLI entrypoint
- [`backend/manager.py`](backend/manager.py:1) – orchestrator workflow + internal state
- [`backend/news_researcher.py`](backend/news_researcher.py:1) – Serper-driven research task
- [`backend/financial_analyst.py`](backend/financial_analyst.py:1) – Alpha Vantage fetch + summary task
- [`backend/report_writer.py`](backend/report_writer.py:1) – memo synthesis + strict template renderer
- [`backend/tools/serper_search.py`](backend/tools/serper_search.py:1) – Serper search integration
- [`backend/tools/alpha_vantage.py`](backend/tools/alpha_vantage.py:1) – Alpha Vantage integration + helpers
- [`backend/schemas.py`](backend/schemas.py:1) – Pydantic schemas for structured handoff

## Configuration (environment variables)

### Option A: set env vars in your shell
Required:
- `OPENAI_API_KEY`
- `SERPER_API_KEY`
- `ALPHAVANTAGE_API_KEY`

OpenAI-compatible configuration:
- `OPENAI_BASE_URL` (optional) – point to OpenAI-compatible gateway (local/hosted)
- `OPENAI_MODEL` (optional, default `gpt-4o-mini`)

Optional:
- `LOG_LEVEL` (default `INFO`)
- `CREW_VERBOSE` (set to `1` to enable CrewAI verbose output)

### Option B: use a local `.env` file
1) Copy [`.env.example`](.env.example:1) to `.env`
2) Fill in your keys

`backend/main.py` loads `.env` automatically via [`dotenv.load_dotenv()`](backend/main.py:1).

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
set OPENAI_API_KEY=...
set SERPER_API_KEY=...
set ALPHAVANTAGE_API_KEY=...
python -m backend.main "Research competitor: Notion. Focus on recent product launches, pricing, and any financial signals."
```

Using an OpenAI-compatible provider:
```bash
set OPENAI_BASE_URL=http://localhost:8080/v1
set OPENAI_MODEL=gpt-4o-mini
python -m backend.main "Research competitor: Notion. Focus on recent product launches, pricing, and any financial signals."
```

## Output
A single formatted memo matching the required template.

Example skeleton (your run will be filled with real findings):

```text
Market Report: **Notion**
date: **January 2025**

**Executive Summary**
- ...

**Company Overview**
- description of the business
  ...
...
```

## Notes
- Recent developments are best-effort from Serper search results (citations are tracked internally in state).
- Alpha Vantage endpoints can rate-limit; the client retries with backoff and returns `unknown` when unavailable.
