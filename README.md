# Smart GitHub Triage Agent

An event-driven AI agent that monitors a GitHub repository, triages incoming issues and pull requests, and presents structured recommendations to maintainers for approval.

**Value prop:** Cut average issue triage time from hours to seconds while keeping maintainers in full control, with auditable reasoning traces for every decision.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
cd dashboard && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required:
- `OPENAI_API_KEY` — OpenAI API key (GPT-4o)
- `GITHUB_TOKEN` — GitHub Personal Access Token (repo scope)
- `GITHUB_WEBHOOK_SECRET` — HMAC secret from your GitHub webhook config

### 3. Seed the vector database (optional but recommended)

```bash
python -m backend.bootstrap your-org/your-repo 500
```

### 4. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Start the dashboard

```bash
cd dashboard && npm run dev
```

### 6. Configure GitHub webhook

Point your GitHub webhook to: `http://your-server:8000/webhook`
Content type: `application/json`
Secret: (your `GITHUB_WEBHOOK_SECRET`)
Events: `issues` (opened), `pull_request` (opened)

For local testing, use [ngrok](https://ngrok.com/):
```bash
ngrok http 8000
```

## Architecture

```
GitHub (webhooks) → FastAPI → LangGraph → (LLM + Vector Search + GitHub API) → Dashboard
```

- **Backend:** Python 3.11+, FastAPI, LangGraph, Chroma, SQLite
- **Frontend:** React + TypeScript + Tailwind + WebSocket
- **LLM:** OpenAI GPT-4o with structured output
- **Embeddings:** paraphrase-multilingual-MiniLM-L12-v2 (50+ languages)
- **Vector DB:** Chroma (embedded, zero-ops)

## Key Features

- **Issue & PR triage** — analyzes content, suggests labels, priority, and draft comments
- **Multi-language support** — detects and translates ES, ZH, JA, FR, DE
- **Similarity search** — finds duplicate and related issues via vector embeddings
- **Auto-label** — applies labels at >=95% confidence (toggleable)
- **Real-time dashboard** — WebSocket-powered live progress updates
- **Reasoning trace** — color-coded timeline of every AI decision step
- **Comment edit diff** — shows what maintainers changed before approval
- **Full audit trail** — every step logged with trace IDs and timestamps

## Project Structure

```
backend/
├── main.py              # FastAPI app (webhook + dashboard API + WebSocket)
├── config.py            # Pydantic BaseSettings configuration
├── orchestrator.py      # LangGraph state machine
├── llm_service.py       # LLM calls with retry + fallback
├── github_tools.py      # GitHub API wrapper
├── vector_db.py         # Chroma operations
├── language.py          # Language detection + translation
├── policy.py            # Rule-based safety layer
├── bootstrap.py         # Vector DB seeding
├── prompts.py           # All prompt templates
├── models.py            # Pydantic models
├── database.py          # SQLite operations
├── logging_config.py    # JSON structured logging
└── tests/               # Unit + integration tests

dashboard/
├── src/
│   ├── App.tsx          # Main app with routing
│   ├── pages/           # Dashboard pages
│   ├── hooks/           # WebSocket hook
│   └── utils/           # API client
└── package.json
```

## Demo Strategy

1. Pre-seed a demo repo with 50+ issues
2. Prepare 5 test issues: clear bug, duplicate, vague, feature request, empty
3. Open an issue live during the demo — watch it appear on the dashboard in real-time
4. Show the reasoning trace, approve, and verify on GitHub
5. Display metrics: accuracy, time-to-triage, approval rate

## License

MIT
