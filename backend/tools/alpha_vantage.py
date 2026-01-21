from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx


class AlphaVantageError(RuntimeError):
    pass


@dataclass
class AlphaVantageClient:
    api_key: str
    base_url: str = "https://www.alphavantage.co/query"
    timeout_s: float = 25.0

    @staticmethod
    def from_env() -> "AlphaVantageClient":
        key = os.getenv("ALPHAVANTAGE_API_KEY")
        if not key:
            raise AlphaVantageError("ALPHAVANTAGE_API_KEY is required")
        return AlphaVantageClient(api_key=key)

    def _get(self, params: Dict[str, Any], *, max_retries: int = 2) -> Dict[str, Any]:
        last_err: Optional[BaseException] = None
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    resp = client.get(self.base_url, params={**params, "apikey": self.api_key})
                    resp.raise_for_status()
                    data = resp.json()

                if isinstance(data, dict) and (
                    "Information" in data or "Note" in data or "Error Message" in data
                ):
                    # Rate limits / errors are returned in JSON with 200.
                    msg = data.get("Information") or data.get("Note") or data.get("Error Message")
                    if msg:
                        # Don't retry for daily-limit messages; it will never succeed.
                        if "per day" in str(msg).lower():
                            raise AlphaVantageError(str(msg))
                        time.sleep(1.2 * (attempt + 1))
                        raise AlphaVantageError(str(msg))

                return data
            except Exception as e:  # noqa: BLE001
                last_err = e
                if attempt < max_retries:
                    time.sleep(1.2 * (attempt + 1))
                    continue
        raise AlphaVantageError(f"Alpha Vantage request failed: {last_err}")

    def symbol_search(self, keywords: str) -> List[Dict[str, Any]]:
        data = self._get({"function": "SYMBOL_SEARCH", "keywords": keywords})
        return data.get("bestMatches", []) or []

    def overview(self, symbol: str) -> Dict[str, Any]:
        return self._get({"function": "OVERVIEW", "symbol": symbol})

    def income_statement(self, symbol: str) -> Dict[str, Any]:
        return self._get({"function": "INCOME_STATEMENT", "symbol": symbol})

    def cash_flow(self, symbol: str) -> Dict[str, Any]:
        return self._get({"function": "CASH_FLOW", "symbol": symbol})

    def earnings(self, symbol: str) -> Dict[str, Any]:
        return self._get({"function": "EARNINGS", "symbol": symbol})

    def time_series_daily_adjusted(self, symbol: str) -> Dict[str, Any]:
        return self._get({"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol})


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s in {"", "None", "null", "-"}:
            return None
        return float(s)
    except Exception:  # noqa: BLE001
        return None


def _fmt_money(v: Optional[float]) -> str:
    if v is None or math.isnan(v):
        return "unknown"
    abs_v = abs(v)
    if abs_v >= 1e12:
        return f"${v/1e12:.2f}T"
    if abs_v >= 1e9:
        return f"${v/1e9:.2f}B"
    if abs_v >= 1e6:
        return f"${v/1e6:.2f}M"
    if abs_v >= 1e3:
        return f"${v/1e3:.2f}K"
    return f"${v:.0f}"


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (a - b) / b * 100.0


def summarize_price_performance(
    ts_daily_adjusted: Dict[str, Any],
) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float], Optional[float]]:
    series = ts_daily_adjusted.get("Time Series (Daily)") or {}
    if not isinstance(series, dict) or not series:
        return None, None, None, None, None

    dates = sorted(series.keys(), reverse=True)
    as_of = dates[0]

    def close_at(idx: int) -> Optional[float]:
        if idx >= len(dates):
            return None
        row = series.get(dates[idx]) or {}
        return _safe_float(row.get("5. adjusted close") or row.get("4. close"))

    last = close_at(0)
    c_5d = close_at(5)
    c_1m = close_at(22)
    c_6m = close_at(126)

    return as_of, last, _pct(last, c_5d), _pct(last, c_1m), _pct(last, c_6m)


def summarize_revenue_growth(income_statement: Dict[str, Any]) -> Tuple[str, str]:
    annual = income_statement.get("annualReports") or []
    if not isinstance(annual, list) or len(annual) < 2:
        return "unknown", "unknown"

    def rev(report: Dict[str, Any]) -> Optional[float]:
        return _safe_float(report.get("totalRevenue"))

    r0 = rev(annual[0])
    r1 = rev(annual[1])
    revenue = _fmt_money(r0)
    g = _pct(r0, r1)
    growth = f"{g:.1f}% YoY" if g is not None else "unknown"
    return revenue, growth


def summarize_free_cash_flow(cash_flow: Dict[str, Any]) -> str:
    """Best-effort free cash flow summary.

    Alpha Vantage `CASH_FLOW` provides `annualReports` and `quarterlyReports`.
    We use the latest annual `operatingCashflow` and `capitalExpenditures` to
    compute a simple FCF proxy: OCF - CapEx.

    Returns a human-readable string, or "unknown".
    """

    annual = cash_flow.get("annualReports") or []
    if not isinstance(annual, list) or not annual:
        return "unknown"

    latest = annual[0] or {}
    ocf = _safe_float(latest.get("operatingCashflow"))
    capex = _safe_float(latest.get("capitalExpenditures"))
    if ocf is None or capex is None:
        return "unknown"

    fcf = ocf - capex
    return f"FCF (annual): {_fmt_money(fcf)}"
