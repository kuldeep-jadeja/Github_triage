# Research Summary — Smart GitHub Triage Agent

## Stack
**Backend:** FastAPI + Uvicorn (Python 3.11+) — async-native, well-documented, standard for Python APIs
**Orchestration:** LangGraph 1.1.4+ — state machine with error paths justifies the complexity
**Vector DB:** ChromaDB (embedded) — zero-ops, local, no external service needed
**Embeddings:** paraphrase-multilingual-MiniLM-L12-v2 — 50+ language support, fast, free
**GitHub API:** PyGithub 2.9.0 — standard Python GitHub client
**Frontend:** React + Vite + TypeScript + Tailwind + WebSocket
**Database:** SQLite (hackathon) → PostgreSQL + pgvector (production)
**Deployment:** Docker Compose, multi-stage builds

## Table Stakes
- Auto-labeling from existing label set
- Duplicate detection via similarity search
- Priority suggestion (P0-P3) with reasoning
- Missing info detection and clarifying questions
- Response drafting in professional tone
- Configurable automation levels (human-in-loop)
- Full audit trail with reasoning traces
- Confidence scoring with escalation

## Differentiators
- Multi-language support (ES, ZH, JA, FR, DE)
- Real-time triage dashboard with WebSocket
- PR triage with diff analysis and reviewer suggestions
- Issue template validation
- Comment edit diff (show what maintainer changed)
- Metrics panel (accuracy, time-to-triage, approval rate)
- Auto-label at high confidence (>=0.95)
- Cost-aware processing with token tracking

## Watch Out For
1. **Prompt injection** via issue content — use `<user_input>` and `<reference_data>` tags
2. **LLM hallucination** of labels — post-validation against allowlist
3. **GitHub API rate limits** — 3 concurrent workers max, token bucket
4. **Webhook duplicates** — idempotency via issue_id with atomic insert
5. **Embedding dimension mismatch** — single source of truth, startup validation
6. **Context window overflow** — truncate to 3000 chars, note in trace
7. **Demo-day failures** — canned demo mode, recorded video backup
8. **SQLite write contention** — serialized writes fine at 3 workers

## Architecture Pattern
Event-driven pipeline: Webhook → Signature Verify → Async Queue → LangGraph State Machine → (LLM + Vector Search + GitHub API) → Policy Engine → (Auto-Label | Human Review) → Execute → Log

## Market Gap
Existing tools are either cheap dumb labelers (Probot) or expensive autonomous resolvers. The sweet spot is an intelligent triage agent with human-in-the-loop that keeps maintainers in control while dramatically reducing triage time.
