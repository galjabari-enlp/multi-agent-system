from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.config import load_config
from backend.main import _build_llm
from backend.manager import run_manager_workflow

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    chat_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    chat_id: str


def create_app() -> FastAPI:
    # Ensure UTF-8 output on Windows terminals to avoid CrewAI event bus
    # UnicodeEncodeError when agents emit emoji/typographic characters.
    try:  # pragma: no cover
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    # Loads a local .env file if present (safe no-op in production environments).
    load_dotenv(override=False)

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    app = FastAPI(title="multi-agent-system API", version="0.1.0")

    cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

    # Dev default for Vite
    if not cors_origins:
        cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        # Keep API stateless for now; frontend manages session history.
        chat_id = (req.chat_id or "").strip() or "local"

        # Ensure config loads (validates env vars) early with a nice error.
        _ = load_config()

        llm = _build_llm()
        result = run_manager_workflow(competitor_prompt=req.message, llm=llm)

        # For both simple_fact and full_report, we return a `reply` string.
        return ChatResponse(reply=result.memo_markdown, chat_id=chat_id)

    return app


app = create_app()
