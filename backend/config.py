from __future__ import annotations

import os

from backend.schemas import AlphaVantageConfig, AppConfig, LLMConfig, SerperConfig


def load_config() -> AppConfig:
    # Ensure .env is loaded even when this module is imported outside
    # [`backend.main.main()`](backend/main.py:29) (e.g. in quick one-off scripts).
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except Exception:
        # If python-dotenv isn't available, we just rely on real environment vars.
        pass

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    # Treat empty/whitespace-only OPENAI_BASE_URL as unset.
    base_url_raw = os.getenv("OPENAI_BASE_URL")
    base_url = (base_url_raw or "").strip() or None

    return AppConfig(
        llm=LLMConfig(
            api_key=openai_api_key,
            base_url=base_url,
            model=os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
        ),
        serper=SerperConfig(api_key=os.getenv("SERPER_API_KEY") or ""),
        alpha_vantage=AlphaVantageConfig(api_key=os.getenv("ALPHAVANTAGE_API_KEY") or ""),
    )
