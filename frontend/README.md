# Multi-Agent Frontend (Chat UI)

ChatGPT-style chat UI themed like Interactive Brokers (dark/black UI with red accents).

## Tech
- Vite + React + TypeScript + Tailwind
- Markdown rendering: `react-markdown` + `remark-gfm`

## Setup

```bash
cd frontend
npm install
```

## Environment variables

Create `frontend/.env` (or set env vars in your shell) with:

```env
VITE_API_BASE_URL=http://localhost:8000
```

If not set, the UI defaults to `http://localhost:8000`.

## Run

### 1) Start backend API

From repo root:

```bash
pip install -r requirements.txt
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Backend endpoints:
- `GET /health`
- `POST /api/chat` with body:

```json
{ "message": "Research Nvidia ticker NVDA", "chat_id": "chat_..." }
```

Response:

```json
{ "reply": "<markdown>", "chat_id": "chat_..." }
```

### 2) Start frontend

```bash
cd frontend
npm run dev
```

Open the printed URL (typically `http://localhost:5173`).

## CORS requirements

When running frontend and backend on different origins, backend must send CORS headers.
This repo configures FastAPI CORS in [`backend/api.py`](../backend/api.py:1).

To customize allowed origins, set:

```env
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## Notes
- Chat history is session-local and stored in `localStorage`.
- No authentication.
- The backend is treated as stateless; frontend maintains the conversation history.
