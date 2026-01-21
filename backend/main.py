from __future__ import annotations

import argparse
import logging
import os
import sys

from crewai.llm import LLM
from dotenv import load_dotenv

# NOTE:
# Prefer running as a module: `python -m backend.main`.
# When running as a script (e.g. `python backend/main.py`), Python sets sys.path[0]
# to the `backend/` directory, which makes absolute imports like `from backend...`
# fail because the project root isn't on sys.path.
# This fallback prepends the project root to sys.path so `python backend/main.py`
# works for local dev.
try:
    from backend.config import load_config
    from backend.manager import run_manager_workflow
except ModuleNotFoundError:  # pragma: no cover
    import pathlib

    _PROJECT_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

    from backend.config import load_config  # type: ignore[no-redef]
    from backend.manager import run_manager_workflow  # type: ignore[no-redef]


def _build_llm() -> LLM:
    cfg = load_config().llm

    # Possible sources of the failures we've seen:
    # 1) LiteLLM doesn't recognize gateway model ids like `openai.openai/...`.
    # 2) The gateway doesn't recognize LiteLLM-style ids like `openai/...`.
    # 3) Wrong base_url / path handling.
    # 4) Missing headers/auth required by gateway.
    # 5) Wrong endpoint (chat/completions vs v1/chat/completions).
    # 6) API key lacks access to the model.
    # 7) Encoding issues breaking event logging (separate issue).
    #
    # Most likely: (1) and (2) simultaneously.
    # To satisfy *both* sides, we do this:
    # - Send LiteLLM a provider-prefixed model (`openai/<name>`) so it selects OpenAI.
    # - Point LiteLLM/OpenAI at your gateway via base_url.
    # - Override the model actually sent on the wire via `extra_body` so the gateway
    #   receives its expected id (`openai.openai/<name>`).

    model_gateway = cfg.model.strip()

    # Derive the LiteLLM/provider model name from the gateway id.
    model_for_litellm = model_gateway
    if model_for_litellm.startswith("openai.openai/"):
        model_for_litellm = "openai/" + model_for_litellm.removeprefix("openai.openai/")
    elif model_for_litellm.startswith("google_genai.gemini/"):
        model_for_litellm = "gemini/" + model_for_litellm.removeprefix("google_genai.gemini/")
    elif model_for_litellm.startswith("xai.xai/"):
        model_for_litellm = "xai/" + model_for_litellm.removeprefix("xai.xai/")

    # Per your instruction: use this base url for LiteLLM too.
    base_url = "https://chat.velocity.online/api"

    logging.getLogger(__name__).info(
        "LLM config resolved: model_gateway=%r model_for_litellm=%r base_url=%r",
        model_gateway,
        model_for_litellm,
        base_url,
    )

    llm = LLM(
        model=model_for_litellm,
        api_key=cfg.api_key,
        base_url=base_url,
        temperature=cfg.temperature,
        # Send gateway model id in the request body (OpenAI supports `extra_body`)
        # so the proxy can route correctly.
        extra_body={"model": model_gateway},
    )
    return llm


def main(argv: list[str] | None = None) -> int:
    # Loads a local .env file if present (safe no-op in production environments).
    load_dotenv(override=False)

    parser = argparse.ArgumentParser(description="CrewAI competitor market report generator")
    parser.add_argument(
        "competitor_prompt",
        type=str,
        nargs="?",
        help="User prompt containing competitor/company name and optional context",
    )
    args = parser.parse_args(argv)

    competitor_prompt = args.competitor_prompt or os.getenv("COMPETITOR_PROMPT")
    if not competitor_prompt:
        print(
            "Missing competitor_prompt. Provide as CLI arg or set COMPETITOR_PROMPT env var.",
            file=sys.stderr,
        )
        return 2

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    llm = _build_llm()
    result = run_manager_workflow(competitor_prompt=competitor_prompt, llm=llm)
    print(result.memo_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
