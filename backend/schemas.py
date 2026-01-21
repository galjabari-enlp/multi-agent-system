from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str = Field(..., description="Page title")
    url: str = Field(..., description="Canonical URL")
    snippet: Optional[str] = Field(None, description="Search snippet")
    published_date: Optional[str] = Field(
        None,
        description="Published date if detectable (best effort, may be None)",
    )


class CompanyOverview(BaseModel):
    description: str = Field(..., description="What the company does")
    founded: str = Field("unknown", description="Founded year/date")
    hq_location: str = Field("unknown", description="HQ location")
    employees: str = Field("unknown", description="Headcount if available")
    executives: List[str] = Field(default_factory=list, description="Key leaders")


class RecentDevelopments(BaseModel):
    product_news: List[str] = Field(default_factory=list)
    partnerships_and_deals: List[str] = Field(default_factory=list)
    org_changes: List[str] = Field(default_factory=list)


class ProductsPricing(BaseModel):
    core_products: List[str] = Field(default_factory=list)
    pricing_model: str = Field("unknown")
    competitive_differentiation: List[str] = Field(default_factory=list)


class NewsResearchResult(BaseModel):
    company_overview: CompanyOverview
    recent_developments: RecentDevelopments
    products_pricing: ProductsPricing
    sources: List[Source] = Field(default_factory=list)


class PricePerformance(BaseModel):
    as_of: str
    last_close: Optional[float] = None
    change_5d_pct: Optional[float] = None
    change_1m_pct: Optional[float] = None
    change_6m_pct: Optional[float] = None


class FinancialOverview(BaseModel):
    ticker: str = Field("unknown")
    market_cap: str = Field("unknown")
    revenue: str = Field("unknown")
    revenue_growth: str = Field("unknown")
    profitability: str = Field("unknown")
    burn_rate: str = Field("unknown")
    funding_and_valuation: str = Field("unknown")
    price_performance: Optional[PricePerformance] = None
    notes: List[str] = Field(default_factory=list)


class FinancialAnalysisResult(BaseModel):
    financial_overview: FinancialOverview
    sources: List[Source] = Field(default_factory=list)


class ManagerParsedPrompt(BaseModel):
    competitor_name: str
    ticker: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    time_horizon: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class ManagerState(BaseModel):
    competitor_name: str
    parsed_prompt: ManagerParsedPrompt
    company_overview: Optional[CompanyOverview] = None
    recent_developments: Optional[RecentDevelopments] = None
    products_pricing: Optional[ProductsPricing] = None
    financial_overview: Optional[FinancialOverview] = None
    sources: List[Source] = Field(default_factory=list)


class ReportMemo(BaseModel):
    competitor_name: str
    date_label: str = Field("January 2025")
    executive_summary: List[str]
    company_overview: CompanyOverview
    recent_developments: RecentDevelopments
    financial_overview: FinancialOverview
    products_pricing: ProductsPricing
    swot: Dict[Literal["strengths", "weaknesses", "opportunities", "threats"], List[str]]
    key_takeaways: List[str]

    def render_markdown(self) -> str:
        def bullets(items: List[str]) -> str:
            return "\n".join([f"- {i}" for i in items]) if items else "- unknown"

        co = self.company_overview
        rd = self.recent_developments
        pp = self.products_pricing
        fo = self.financial_overview

        lines: List[str] = []
        lines.append(f"Market Report: **{self.competitor_name}**")
        lines.append(f"date: **{self.date_label}**")
        lines.append("")
        lines.append("**Executive Summary**")
        lines.append(bullets(self.executive_summary))
        lines.append("")
        lines.append("**Company Overview**")
        lines.append(f"- description of the business  \n  {co.description}")
        lines.append(f"- founded (year/date)  \n  {co.founded}")
        lines.append(f"- location  \n  {co.hq_location}")
        lines.append(f"- employees (headcount)  \n  {co.employees}")
        lines.append(
            "- executives/leadership (CEO, founders)  \n  "
            + ("; ".join(co.executives) if co.executives else "unknown")
        )
        lines.append("")
        lines.append("**Recent Developments**")
        lines.append("- product news/updates / new products")
        lines.append(bullets(rd.product_news))
        lines.append("- partnerships and deals")
        lines.append(bullets(rd.partnerships_and_deals))
        lines.append("- organizational changes")
        lines.append(bullets(rd.org_changes))
        lines.append("")
        lines.append("**Financial Overview**")
        lines.append("- revenue & growth")
        lines.append(f"- {fo.revenue} | growth: {fo.revenue_growth}")
        lines.append("- funding & valuation")
        lines.append(f"- {fo.funding_and_valuation}")
        lines.append("- profitability & burn rate")
        lines.append(f"- profitability: {fo.profitability} | burn rate: {fo.burn_rate}")
        if fo.price_performance:
            perf = fo.price_performance
            lines.append(
                f"- price performance (as of {perf.as_of}): last close {perf.last_close}; "
                f"5d {perf.change_5d_pct}%; 1m {perf.change_1m_pct}%; 6m {perf.change_6m_pct}%"
            )
        if fo.notes:
            lines.append("- notes")
            lines.append(bullets(fo.notes))
        lines.append("")
        lines.append("**Products & Pricing**")
        lines.append("- core products")
        lines.append(bullets(pp.core_products))
        lines.append("- pricing model")
        lines.append(f"- {pp.pricing_model}")
        lines.append("- competitive differentiation")
        lines.append(bullets(pp.competitive_differentiation))
        lines.append("")
        lines.append("**SWOT Analysis**")
        lines.append("- strengths (internal +)")
        lines.append(bullets(self.swot.get("strengths", [])))
        lines.append("- weaknesses (internal -)")
        lines.append(bullets(self.swot.get("weaknesses", [])))
        lines.append("- opportunities (external +)")
        lines.append(bullets(self.swot.get("opportunities", [])))
        lines.append("- threats (external -)")
        lines.append(bullets(self.swot.get("threats", [])))
        lines.append("")
        lines.append("**Key Takeaways**")
        lines.append(bullets(self.key_takeaways))
        return "\n".join(lines)


class LLMConfig(BaseModel):
    api_key: str
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.2


class SerperConfig(BaseModel):
    api_key: str


class AlphaVantageConfig(BaseModel):
    api_key: str


class AppConfig(BaseModel):
    llm: LLMConfig
    serper: SerperConfig
    alpha_vantage: AlphaVantageConfig


class ToolError(BaseModel):
    provider: str
    message: str
    details: Optional[Dict[str, Any]] = None
