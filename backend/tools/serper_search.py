from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.schemas import Source


class SerperSearchError(RuntimeError):
    pass


def _env_api_key(explicit_api_key: Optional[str]) -> str:
    api_key = explicit_api_key or os.getenv("SERPER_API_KEY")
    if not api_key:
        raise SerperSearchError("SERPER_API_KEY is required")
    return api_key


def serper_search(
    query: str,
    *,
    api_key: Optional[str] = None,
    num: int = 10,
    gl: str = "us",
    hl: str = "en",
    timeout_s: float = 20.0,
    max_retries: int = 2,
) -> List[Source]:
    """Search via Serper (Google Search API). Returns a list of Sources.

    Docs: https://serper.dev/
    Endpoint: POST https://google.serper.dev/search
    """

    key = _env_api_key(api_key)
    url = "https://google.serper.dev/search"

    payload = {"q": query, "num": num, "gl": gl, "hl": hl}
    headers = {"X-API-KEY": key, "Content-Type": "application/json"}

    last_err: Optional[BaseException] = None
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    # best-effort backoff
                    time.sleep(1.5 * (attempt + 1))
                    raise SerperSearchError("Serper rate limit (429)")
                resp.raise_for_status()
                data = resp.json()

            organic = data.get("organic", []) or []
            sources: List[Source] = []
            for item in organic:
                link = item.get("link")
                title = item.get("title")
                snippet = item.get("snippet")
                date = item.get("date")
                if not link or not title:
                    continue
                sources.append(
                    Source(title=str(title), url=str(link), snippet=snippet, published_date=date)
                )
            return sources
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue

    raise SerperSearchError(
        f"Serper search failed for query={json.dumps(query)}: {last_err}"
    )
