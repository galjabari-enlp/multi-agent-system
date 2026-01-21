from __future__ import annotations

import json
from typing import List, Optional

from crewai import Agent, Task

from backend.schemas import FinancialAnalysisResult, FinancialOverview, PricePerformance, Source
from backend.tools.alpha_vantage import (
    AlphaVantageClient,
    summarize_price_performance,
    summarize_revenue_growth,
)


def build_financial_analyst_agent(llm) -> Agent:
    return Agent(
        role="FinancialAnalyst",
        goal="Pull financial/market data via Alpha Vantage and summarize key financial signals.",
        backstory=(
            "You are a disciplined financial analyst. You do not invent numbers. "
            "If Alpha Vantage lacks fields, you return 'unknown' and explain." 
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def _resolve_ticker(client: AlphaVantageClient, competitor_name: str) -> Optional[str]:
    """Resolve a best-effort *primary* ticker for a company name.

    Alpha Vantage SYMBOL_SEARCH frequently returns multiple listings across regions
    (e.g., Frankfurt, XETRA, etc.). Picking the first result is often wrong.

    Heuristics:
    - Prefer United States equities when available.
    - Prefer symbols without exchange suffixes (e.g., "AVGO" over "1YD.FRK" or "AVGO34.SAO").
    - If still tied, take the highest matchScore.
    """

    matches = client.symbol_search(competitor_name)
    if not matches:
        return None

    def s(m: dict, key: str) -> str:
        v = m.get(key)
        return str(v).strip() if v is not None else ""

    def score(m: dict) -> float:
        try:
            return float(s(m, "9. matchScore") or "0")
        except Exception:  # noqa: BLE001
            return 0.0

    def is_us_equity(m: dict) -> bool:
        return s(m, "3. type").lower() == "equity" and s(m, "4. region").lower() == "united states"

    def is_plain_symbol(m: dict) -> bool:
        sym = s(m, "1. symbol") or s(m, "symbol")
        # Plain US tickers are typically like AAPL, NVDA, BRK.B
        return bool(sym) and ("." not in sym) and ("/" not in sym)

    # Sort by: US equity first, plain symbol next, higher matchScore last (desc)
    ranked = sorted(
        matches,
        key=lambda m: (
            0 if is_us_equity(m) else 1,
            0 if is_plain_symbol(m) else 1,
            -score(m),
        ),
    )

    top = ranked[0]
    symbol = top.get("1. symbol") or top.get("symbol")
    return str(symbol).strip() or None


def _fetch_financials(
    *,
    competitor_name: str,
    ticker: Optional[str],
) -> FinancialAnalysisResult:
    client = AlphaVantageClient.from_env()

    resolved = ticker or _resolve_ticker(client, competitor_name)
    if not resolved:
        fo = FinancialOverview(
            ticker="unknown",
            market_cap="unknown",
            revenue="unknown",
            revenue_growth="unknown",
            profitability="unknown",
            burn_rate="unknown",
            funding_and_valuation="unknown",
            notes=[
                "Ticker not found via Alpha Vantage SYMBOL_SEARCH; treating as private/unknown market data."
            ],
        )
        return FinancialAnalysisResult(financial_overview=fo, sources=[])

    overview = client.overview(resolved)
    income = client.income_statement(resolved)

    market_cap = overview.get("MarketCapitalization")
    revenue_ttm = overview.get("RevenueTTM") or overview.get("RevenuePerShareTTM")

    revenue, growth = summarize_revenue_growth(income)
    if revenue == "unknown" and revenue_ttm:
        # RevenueTTM is typically a number string.
        try:
            revenue = f"${float(revenue_ttm)/1e9:.2f}B (TTM)"
        except Exception:  # noqa: BLE001
            revenue = str(revenue_ttm)

    profit_margin = overview.get("ProfitMargin")
    op_margin = overview.get("OperatingMarginTTM")
    profitability = "unknown"
    if profit_margin or op_margin:
        profitability = f"profit margin: {profit_margin or 'unknown'}; operating margin: {op_margin or 'unknown'}"

    # Market cap formatting best-effort
    mcap_str = "unknown"
    try:
        if market_cap:
            mcap_str = f"${float(market_cap)/1e9:.2f}B"
    except Exception:  # noqa: BLE001
        mcap_str = str(market_cap)

    # Price performance
    perf_obj: Optional[PricePerformance] = None
    try:
        ts = client.time_series_daily_adjusted(resolved)
        as_of, last, p5, p1m, p6m = summarize_price_performance(ts)
        if as_of:
            perf_obj = PricePerformance(
                as_of=as_of,
                last_close=last,
                change_5d_pct=None if p5 is None else round(p5, 2),
                change_1m_pct=None if p1m is None else round(p1m, 2),
                change_6m_pct=None if p6m is None else round(p6m, 2),
            )
    except Exception:  # noqa: BLE001
        perf_obj = None

    fo = FinancialOverview(
        ticker=resolved,
        market_cap=mcap_str,
        revenue=revenue,
        revenue_growth=growth,
        profitability=profitability,
        burn_rate="unknown",
        funding_and_valuation=(
            f"public markets (market cap {mcap_str})" if mcap_str != "unknown" else "unknown"
        ),
        price_performance=perf_obj,
        notes=[
            "Alpha Vantage provides limited fundamentals for some tickers; unknown fields reflect missing data.",
        ],
    )

    # Alpha Vantage is not a web source; we keep sources empty to satisfy template.
    return FinancialAnalysisResult(financial_overview=fo, sources=[])


def build_financial_task(
    agent: Agent,
    *,
    competitor_name: str,
    ticker: Optional[str],
) -> Task:
    data = _fetch_financials(competitor_name=competitor_name, ticker=ticker)

    prompt = f"""
You are the FinancialAnalyst.

You have already pulled Alpha Vantage data programmatically.

Return ONLY valid JSON matching this schema:
{FinancialAnalysisResult.model_json_schema()}

Do not add extra keys.

COMPANY: {competitor_name}
TICKER (optional): {ticker}

DATA:
{json.dumps(data.model_dump(), indent=2)}
""".strip()

    return Task(
        description=prompt,
        expected_output="JSON matching FinancialAnalysisResult schema",
        agent=agent,
        output_json=FinancialAnalysisResult,
    )
