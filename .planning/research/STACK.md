# Stack Research — AI GitHub Triage Agent

*Research date: April 2, 2026*

---

## 1. Backend Framework

**Recommendation:** FastAPI 0.115+ (with Uvicorn 0.32+)

**Why:**
- Async-native from the ground up — critical for handling concurrent webhook deliveries from GitHub without blocking
- Built-in request validation via Pydantic v2 — GitHub webhook payloads are complex nested JSON; auto-validation eliminates boilerplate
- Automatic OpenAPI/Swagger docs — invaluable for debugging webhook signatures and testing endpoints
- Native WebSocket support — enables real-time dashboard updates without additional libraries
- First-class type hints throughout — catches payload shape mismatches at development time, not runtime
- Massive ecosystem momentum: 38.7M+ monthly PyPI downloads for the LangGraph ecosystem alone shows FastAPI is the de facto Python API framework in 2026
- Tested pattern: FastAPI + WebSockets for real-time AI dashboards is a well-documented 2026 pattern with production-ready reconnect logic, backpressure handling, and auth patterns

**Alternatives considered:**
- **Flask 3.x** — synchronous by default, requires gevent/eventlet for async, no built-in WebSocket support, no auto-validation. Fine for simple APIs but a poor fit for webhook-heavy async workloads.
- **Django 5.x + Django Ninja** — Django Ninja adds FastAPI-like syntax but inherits Django heavier ORM/templating overhead. Overkill for a webhook-receiving microservice. Django Channels for WebSockets adds operational complexity.
- **Starlette** — FastAPI is built on Starlette; using Starlette directly means re-implementing validation, docs, and dependency injection that FastAPI gives free.
- **Litestar** — technically excellent but significantly smaller community, fewer integrations, and less battle-tested for production webhook handling.

---

## 2. LLM Orchestration Framework

**Recommendation:** LangGraph 1.1.4+

**Why:**
- Graph-based state machine model — GitHub issue triage has inherently branching logic (classify, route, label, assign, escalate) that maps naturally to directed graphs with conditional edges
- Built-in checkpointing — if the triage pipeline crashes mid-way through a 10-step review, it resumes from the last checkpoint, not from scratch. Critical for workflows involving human-in-the-loop approval
- Model-agnostic — use Claude for reasoning, GPT for code analysis, and a fine-tuned 7B model for classification, all in the same workflow. Avoids vendor lock-in
- Native human-in-the-loop interrupts — pause the graph for maintainer review at critical junctures (e.g., auto-closing issues, applying sensitive labels), then resume
- LangSmith integration — full execution traces showing every node entry, state mutation, and LLM call. When triage makes a wrong decision, you can trace exactly which step failed
- 38.7M+ monthly PyPI downloads, 28K GitHub stars, adopted by Klarna, Replit, Uber, LinkedIn
- Production-grade: durable execution, state rollback, error recovery are built-in, not bolted on

**Alternatives considered:**
- **LangChain (core)** — LangChain is the component library (chains, prompts, tool integrations); LangGraph is the orchestration layer. Use LangChain tool ecosystem WITH LangGraph, not instead of it. LangChain alone lacks state machines, checkpointing, and conditional branching.
- **CrewAI** — excellent for role-based multi-agent prototyping (44.6K GitHub stars), but its sequential/hierarchical process model cannot express the conditional branching and state rollback that triage workflows require. Teams consistently migrate from CrewAI to LangGraph when control flow complexity increases.
- **OpenAI Agents SDK** — fastest path to a working agent if committed to OpenAI models only, but vendor-locked. No built-in checkpointing or state persistence. The handoff pattern is too simple for triage branching logic.
- **Custom state machines** — possible but you would rebuild checkpointing, observability, and error recovery from scratch. LangGraph 1-2 week learning curve pays dividends over months of custom infrastructure maintenance.
- **Microsoft Agent Framework** — hit RC in February 2026, promising A2A/MCP/AG-UI protocol support, but API still needs to stabilize through production cycles. Watch for GA; not recommended for greenfield projects yet.

---

## 3. Vector Database (Local/Embedded)

**Recommendation:** ChromaDB (latest stable, embedded mode)

**Why:**
- Embedded deployment (in-process, like SQLite) — no separate database service to manage, monitor, or pay for. Single VPS with 4-8 GB RAM handles millions of embeddings
- Python-native API — zero new query languages, no complex configuration. Your team is productive on day one
- Best-in-class developer experience — from zero to working RAG prototype in minutes, not hours
- No network latency — queries are in-process memory lookups, not HTTP round-trips
- Production-ready despite its dev tool reputation — deployed in production across legal AI, financial platforms, and educational products
- Cost: under 0/month on a single modest VPS for corpora up to a few million chunks
- Clean filtering API — sufficient for triage use cases (filter by repo, label, date range, author)

**Alternatives considered:**
- **FAISS** — Meta library is a vector search engine, not a database. No persistence layer, no metadata filtering, no CRUD operations. You would build all of this yourself. Only use FAISS if you need raw ANN performance in a custom system.
- **Qdrant** — superior metadata filtering (applies filters BEFORE vector search), Rust-based with predictable latency. But adds operational complexity (separate service, Docker container, network overhead) that ChromaDB embedded model avoids. Choose Qdrant only if you need complex multi-tenant isolation or 5M+ vectors.
- **LanceDB** — interesting newcomer with disk-efficient Lance format for larger-than-memory datasets. But ecosystem is younger, fewer LLM framework integrations, smaller community. ChromaDB is more mature for this use case.
- **Pinecone** — fully managed, zero operational overhead, but costs 0-00+/month and grows with data volume. Data residency limitations. Overkill for a self-hosted triage bot.
- **pgvector** — only relevant if you are already running PostgreSQL. See section 7 for the SQLite vs PostgreSQL decision.

---

## 4. Embedding Models (Multi-Language)

**Recommendation:** BGE-M3 via sentence-transformers 5.3.0

**Why:**
- **BGE-M3** supports 100+ languages with a shared semantic space — GitHub issues come in many languages; cross-lingual retrieval (query in English, find relevant issues in Chinese/Japanese/etc.) is a first-class capability
- Multi-granularity: handles inputs from short sentences to full documents up to 8,192 tokens — GitHub issue bodies can be lengthy with stack traces, logs, and code snippets
- Three retrieval modes in one model: dense, multi-vector, and sparse — enables hybrid search without maintaining separate models
- Apache 2.0 license — no commercial restrictions
- **sentence-transformers 5.3.0** (released March 12, 2026) — latest stable, full Transformers v5 compatibility, 18.5K GitHub stars, mature training/inference pipeline
- Easy integration with LangChain/LangGraph via HuggingFaceEmbeddings or SentenceTransformerEmbeddings

**Alternatives considered:**
- **all-mpnet-base-v2** — most downloaded sentence-transformers model, Apache 2.0, excellent for English-only. But limited to 384 token context and weaker multilingual performance. Use only if your repos are exclusively English.
- **gte-multilingual-base** (Alibaba) — 70+ languages, 305M parameters, elastic dense embeddings. Good alternative but BGE-M3 triple-retrieval capability (dense + sparse + multi-vector) gives it an edge for hybrid search.
- **Qwen3-Embedding-0.6B** — 100+ languages, instruction-aware, flexible dimensions (32-1024). Excellent but requires structured prompt formatting for optimal results; slightly more complex integration.
- **EmbeddingGemma-300M** (Google) — ultra-lightweight at 300M params, runs in under 200MB RAM. Best for edge/on-device deployment but limited to 2,048 token context.
- **Jina Embeddings v4** — multimodal (text + images), 30+ languages, but CC-BY-NC-4.0 license restricts commercial use. Avoid unless you have a Jina API agreement.

**Model selection guide:**

| Use Case | Model | Dimensions | Context |
|---|---|---|---|
| Multilingual + hybrid search (default) | BGE-M3 | 1024 | 8,192 |
| English-only, proven | all-mpnet-base-v2 | 768 | 384 |
| Edge/low-resource | EmbeddingGemma-300M | 768 (truncatable) | 2,048 |
| Instruction-tuned | Qwen3-Embedding-0.6B | 32-1024 (flexible) | 8,192 |

---

## 5. GitHub API Python Library

**Recommendation:** PyGithub 2.9.0

**Why:**
- 7.7K GitHub stars, 1.9K forks — largest community and most actively maintained Python GitHub API library
- Latest release v2.9.0 (March 22, 2026) — active development with 2,502 commits
- Full type hints — IDE autocomplete for all GitHub API objects (Issue, Repository, Label, etc.)
- Comprehensive API coverage — repositories, issues, pull requests, labels, webhooks, organizations, actions, projects
- Supports GitHub App authentication, OAuth, and PAT — flexible auth for different deployment scenarios
- Supports GitHub Enterprise — if the triage bot needs to work with self-hosted GitHub instances
- Simple, Pythonic API: Github(auth=auth).get_repo(org/repo).get_issues()
- Well-documented with ReadTheDocs site

**Alternatives considered:**
- **github3.py 3.2.0** — ergonomic design centered around logical API organization, but only 1.3K stars, slower development pace, and the original maintainer published a retrospective in 2024 suggesting reduced activity. PyGithub has 6x the community and more recent releases.
- **httpx/requests + raw REST API** — maximum control but you would re-implement pagination, rate limiting, authentication, and object modeling. Only justified if you need GitHub GraphQL API features not covered by REST.
- **Octokit.py** — smaller community, less feature-complete. Not worth the trade-off.
- **GitHub GraphQL via gql** — useful for complex nested queries (e.g., get all issues with their labels, assignees, and comments in one request), but adds complexity. Use PyGithub for standard operations and drop to GraphQL only for specific complex queries.

---

## 6. Frontend Stack (Real-Time Dashboard)

**Recommendation:** React 19 + Vite 6.2 + TypeScript + Recharts + WebSocket (native)

**Why:**
- **React 19** — stable, mature, with improved concurrent rendering for smooth real-time updates
- **Vite 6.2** — fastest dev server and build tool in 2026, HMR is near-instant, zero-config TypeScript support
- **TypeScript** — type-safe WebSocket message contracts prevent silent runtime failures when backend schema changes. Worth the small setup cost
- **Recharts** — composable charting library built on D3, perfect for triage metrics (issues over time, label distribution, response latency)
- **Native WebSocket API** — no library needed for basic WebSocket connections. Custom useWebSocket hook with exponential backoff reconnect logic is the production pattern
- **FastAPI WebSocket backend** — bidirectional ~10ms latency, supports sending control commands (pause triage, switch model) while receiving streamed metrics
- **Lucide React** — lightweight, consistent icon library for dashboard UI elements

**Architecture pattern:**

React Dashboard (Vite dev server :5173) connects via useWebSocket hook (exponential backoff reconnect) to FastAPI /ws/{client_id} (async generator stream). Recharts components render typed JSON events from the stream.

**Key production patterns:**
- Exponential backoff reconnect (1s, 2s, 4s, 8s, max 30s) — prevents DDoSing your own server after a deploy
- Bounded event buffer (MAX_DATA_POINTS = 60) — prevents OOM from unbounded memory growth in long sessions
- Typed message contracts — TypeScript interfaces matching Pydantic models on the backend
- JWT auth via WebSocket query parameter — secure real-time connections

**Alternatives considered:**
- **Socket.IO** — adds reconnection and rooms out of the box but introduces a dependency on the Socket.IO server library. Native WebSockets + custom hook is simpler and avoids the Socket.IO protocol overhead.
- **Server-Sent Events (SSE)** — simpler for one-way streaming but cannot send control commands from the dashboard to the backend. Triage dashboards need bidirectional communication (pause triage, switch model, trigger re-scan).
- **Next.js** — adds SSR/SSG complexity that a real-time dashboard does not need. Vite + React SPA is simpler and faster for this use case.
- **Svelte/SvelteKit** — excellent developer experience but smaller ecosystem for charting libraries and real-time patterns. React ecosystem maturity wins for production dashboards.

---

## 7. SQLite vs PostgreSQL

**Recommendation:** SQLite (with optional migration path to PostgreSQL + pgvector)

**Why for this use case:**
- **Zero operational overhead** — no separate database process, no connection pooling, no backup procedures. The database is a single file
- **Perfectly adequate scale** — GitHub issue triage deals with thousands to tens of thousands of issues per repository, not millions of rows. SQLite handles this effortlessly
- **ACID compliant** — full transaction support for consistent webhook processing (e.g., atomically record webhook receipt and update triage state)
- **Python native** — sqlite3 module is in the standard library. No additional dependencies
- **ChromaDB compatibility** — ChromaDB embedded mode uses a SQLite-like persistence model; keeping everything embedded means zero network hops
- **Deployment simplicity** — single Docker container for the entire backend. No multi-container database orchestration
- **Backup = file copy** — trivial backup strategy for a single-file database

**When to migrate to PostgreSQL + pgvector:**
- Scale exceeds 5M vectors or 100K+ issues across many repositories
- Need concurrent write access from multiple backend instances
- Require advanced full-text search combining vector similarity with text matching
- Team already has PostgreSQL operational expertise

**If migrating, use pgvector** — adds vector similarity search to PostgreSQL with HNSW indexing. Sub-100ms queries on millions of vectors. But requires careful tuning (maintenance_work_mem, HNSW parameters) and adds operational complexity.

**Alternatives considered:**
- **PostgreSQL from day one** — overkill for a single-repository or small multi-repo triage bot. Adds Docker Compose complexity, connection pooling (PgBouncer), and backup procedures that SQLite does not need.
- **MySQL/MariaDB** — no native vector extension comparable to pgvector. Weaker JSON support. No advantage over PostgreSQL if you are going relational.
- **DuckDB** — excellent for analytical queries on issue data but not designed as an application database. Use DuckDB as a secondary analytics layer if needed, not as the primary store.

---

## 8. Docker Deployment Patterns

**Recommendation:** Docker Compose with multi-stage builds

**Architecture:**

Two-service Docker Compose setup:
- **backend**: FastAPI on port 8000, with volume mount for SQLite + ChromaDB persistence, environment variables for GITHUB_TOKEN and WEBHOOK_SECRET
- **frontend**: nginx serving built React app on port 80, depends on backend

**Backend Dockerfile (FastAPI):**
- Base: python:3.12-slim
- Install requirements with pip --no-cache-dir
- Run uvicorn main:app --host 0.0.0.0 --port 8000

**Frontend Dockerfile (React + nginx):**
- Stage 1 (build): node:22-alpine, npm ci, npm run build
- Stage 2 (production): nginx:alpine, copy dist to /usr/share/nginx/html

**Key patterns:**
- **Multi-stage builds** — frontend: Node.js for build, nginx for serving. Backend: slim Python image with cached pip layer
- **Volume mounts for persistence** — SQLite database and ChromaDB collections survive container restarts
- **Environment variable injection** — GitHub tokens and webhook secrets via .env file, never baked into images
- **nginx reverse proxy** — serves static React assets and proxies /api/* and /ws/* to FastAPI backend
- **Sticky sessions for WebSockets** — if scaling to multiple backend instances, nginx needs ip_hash for WebSocket connection affinity
- **Health checks** — FastAPI health endpoint (/health) for Docker Compose depends_on with condition: service_healthy

**Alternatives considered:**
- **Single-container (serving React from FastAPI)** — possible with StaticFiles middleware but loses nginx static file optimization, gzip, and caching. Fine for development, not ideal for production.
- **Kubernetes** — overkill for a triage bot. Docker Compose handles everything needed for single-server deployment.
- **Docker Swarm** — adds orchestration complexity without meaningful benefit for a 2-service application.
- **Serverless (AWS Lambda, Cloud Run)** — problematic for WebSocket connections (timeout limits) and embedded databases (ephemeral filesystem). Only viable if you externalize ChromaDB to a managed service.

---

## Confidence Levels

| Category | Confidence | Rationale |
|---|---|---|
| **Backend Framework** | **High** | FastAPI is the undisputed standard for async Python APIs in 2026. Versions verified (0.115+). No credible alternative offers the same combination of async support, validation, WebSocket support, and ecosystem. |
| **LLM Orchestration** | **High** | LangGraph 1.1.4 is the production leader for complex stateful workflows. Version verified on PyPI (March 31, 2026). The graph-based model maps directly to triage branching logic. CrewAI and OpenAI SDK are provably weaker for this use case. |
| **Vector Database** | **High** | ChromaDB in embedded mode is the consensus recommendation for local/embedded vector storage in 2026. Production-validated across multiple domains. FAISS is not a database; Qdrant is overkill for this scale. |
| **Embedding Models** | **Medium-High** | BGE-M3 is the strongest all-around multilingual model, but the embedding model space moves fast. Qwen3-Embedding and EmbeddingGemma are strong competitors. Recommend benchmarking BGE-M3 vs. gte-multilingual-base on your specific issue corpus before committing. sentence-transformers 5.3.0 version verified (March 12, 2026). |
| **GitHub API Library** | **High** | PyGithub 2.9.0 version verified (March 22, 2026). 6x the community of github3.py, active development, full type hints. No credible alternative. |
| **Frontend Stack** | **High** | React 19 + Vite + TypeScript + WebSocket is the 2026 standard pattern for real-time dashboards. Version numbers verified from production tutorial (React 19, Vite 6.2, Node 22 LTS). The useWebSocket hook pattern with exponential backoff is production-tested. |
| **Database (SQLite vs PostgreSQL)** | **Medium** | SQLite is the right starting point for this scale, but the decision is highly dependent on actual repository count and issue volume. If the bot manages 50+ repositories with 100K+ total issues, PostgreSQL + pgvector becomes the better choice. Start with SQLite, design the data access layer for easy migration. |
| **Docker Deployment** | **High** | Docker Compose with multi-stage builds is the standard pattern. The FastAPI + React + nginx architecture is well-documented and production-tested. Version numbers verified (Python 3.12-slim, Node 22-alpine, nginx:alpine). |

---

## Complete Dependency List

**Backend:**
- fastapi>=0.115.0
- uvicorn[standard]>=0.32.0
- pydantic>=2.0.0
- websockets>=12.0
- PyGithub>=2.9.0
- langgraph>=1.1.4
- langchain>=0.3.0
- langchain-community>=0.3.0
- sentence-transformers>=5.3.0
- chromadb>=0.5.0
- httpx>=0.27.0
- python-dotenv>=1.0.0

**Frontend:**
- react@19
- vite@6.2
- typescript@5
- recharts@2
- lucide-react@latest

**Infrastructure:**
- python:3.12-slim (backend base image)
- node:22-alpine (frontend build)
- nginx:alpine (frontend serve)

---

## Sources

- LangGraph vs CrewAI vs OpenAI Agents SDK comparison (Particula Tech, March 2026)
- Vector Database Comparison 2026 (4xxi, March 2026)
- Best Open-Source Embedding Models in 2026 (BentoML, October 2025)
- pgvector vs Dedicated Vector Databases (Zen van Riel, April 2026)
- Build a Real-Time AI Dashboard: React + WebSocket + FastAPI 2026 (Markaicode, March 2026)
- PyGithub GitHub repository (v2.9.0, March 2026)
- sentence-transformers GitHub releases (v5.3.0, March 2026)
- langgraph PyPI (v1.1.4, March 2026)
- FastAPI Docker deployment patterns (StackLesson, March 2026)
- Docker full-stack Python development (OneUptime, February 2026)
