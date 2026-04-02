# Smart GitHub Triage Agent

## What This Is

An event-driven AI agent that monitors a GitHub repository, triages incoming issues and pull requests, and presents structured recommendations to maintainers for approval — **never acting unilaterally on destructive actions**.

**Core Value Proposition:** "We cut average issue triage time from hours to seconds while keeping maintainers in full control, with auditable reasoning traces for every decision."

## Context

This is a hackathon project — needs to ship a working demo with impressive live demonstration. The agent demonstrates real agentic properties: autonomy (webhook-triggered), tool use (GitHub API, vector search, LLM), planning (multi-step workflow), reflection (confidence thresholds + self-critique), memory (vector DB + state DB), and human-in-the-loop (dashboard approval gate).

## Tech Stack Decisions

| Component | Choice | Rationale |
|---|---|---|
| Backend | Python 3.11+, FastAPI | Standard, well-documented, async-native |
| Orchestration | LangGraph | State machine with error paths justifies complexity |
| Vector DB | Chroma (persistent client) | Zero-ops, local, no external service |
| Database | SQLite | Zero-ops, single file, sufficient for hackathon |
| LLM | OpenAI GPT-4o | Structured output via Pydantic, reliable |
| Embeddings | paraphrase-multilingual-MiniLM-L12-v2 | 50+ language support for multi-language triage |
| GitHub API | PyGithub | Standard Python GitHub client |
| Frontend | React + Tailwind + WebSocket | Real-time updates for demo impact |
| Auth | PAT for API, GitHub OAuth for dashboard | Fastest setup, upgrade to GitHub App later |
| Deployment | Docker + Docker Compose | Reproducible, Railway/Cloud Run compatible |

## Key Design Decisions

- Return 200 from webhook immediately (<1s), process asynchronously
- Idempotency via issue_id/PR_id check
- 3 concurrent workers max (prevents GitHub API rate limit exhaustion)
- Body truncated to 3000 chars for LLM calls
- Structured output enforcement via OpenAI's response_format + Pydantic
- Label validation post-LLM: filter out hallucinated labels
- Prompt injection defense: `<user_input>` and `<reference_data>` tags
- Auto-label at >=0.95 confidence (env-toggleable)
- SQLite instead of PostgreSQL for hackathon simplicity
- PAT instead of GitHub App for fastest setup

## Scope Boundaries

### In Scope (MVP)
- Issue intake (issues.opened webhook)
- PR intake (pull_request.opened webhook)
- Multi-language support (ES, ZH, JA, FR, DE)
- Similarity search with vector DB
- Label + priority suggestion
- Issue template validation
- Draft comment generation
- Auto-label at high confidence
- Maintainer dashboard with real-time updates
- Comment edit diff view
- Full audit trail with structured logging

### Out of Scope
- Auto-assignment to maintainers — requires expertise mapping not available in hackathon timeframe
- Auto-closing duplicates — too risky for MVP; suggest-only
- Issue edit tracking — adds webhook complexity for marginal demo value
- Multi-repo support — one repo is plenty for a hackathon
- Self-improvement / retraining — stretch goal with honest framing

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **WEBHOOK-01**: Receive and verify GitHub webhook signatures (HMAC-SHA256)
- [ ] **WEBHOOK-02**: Handle issues.opened events with idempotency
- [ ] **WEBHOOK-03**: Handle pull_request.opened events with idempotency
- [ ] **TRIAGE-01**: Extract structured info from issue/PR content
- [ ] **TRIAGE-02**: Detect language and translate non-English content (ES, ZH, JA, FR, DE)
- [ ] **TRIAGE-03**: Search similar past issues via vector embeddings
- [ ] **TRIAGE-04**: Suggest labels from repo's existing label set only
- [ ] **TRIAGE-05**: Assign priority (P0-P3) with reasoning
- [ ] **TRIAGE-06**: Detect missing information and generate specific questions
- [ ] **TRIAGE-07**: Validate against issue templates, flag missing sections
- [ ] **TRIAGE-08**: Extract PR diff summary and suggest reviewers
- [ ] **AUTO-01**: Auto-apply labels when confidence >= 0.95 (toggleable)
- [ ] **DRAFT-01**: Generate friendly, professional draft comments in markdown
- [ ] **DASHBOARD-01**: Show pending triage reviews with agent reasoning
- [ ] **DASHBOARD-02**: Allow approve/edit/reject of triage decisions
- [ ] **DASHBOARD-03**: Real-time updates via WebSocket during triage
- [ ] **DASHBOARD-04**: Show metrics (total triaged, accuracy, time-to-triage)
- [ ] **DASHBOARD-05**: Show comment edit diff when maintainers modify drafts
- [ ] **DASHBOARD-06**: History/audit log of all past triage decisions
- [ ] **EXECUTE-01**: Apply labels via GitHub API on approval
- [ ] **EXECUTE-02**: Post comment via GitHub API on approval
- [ ] **SECURITY-01**: Prompt injection defense via input tagging
- [ ] **SECURITY-02**: GitHub OAuth for dashboard with permission check
- [ ] **SECURITY-03**: WebSocket authentication via session token
- [ ] **LOGGING-01**: Full audit trail with trace_id propagation
- [ ] **LOGGING-02**: JSON structured logging to stdout

### Out of Scope

- Auto-assignment — requires maintainer expertise mapping
- Auto-closing duplicates — too risky, suggest-only is safer
- Issue edit tracking — webhook complexity for marginal value
- Multi-repo support — one repo for hackathon
- Self-improvement/retraining — defer to stretch goals

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| SQLite over PostgreSQL | Zero-ops, sufficient for hackathon scale | — Pending |
| PAT over GitHub App | Fastest setup, upgrade later | — Pending |
| LangGraph over function chain | Non-trivial state machine with error paths | — Pending |
| Multilingual embedding model | Required for multi-language scope | — Pending |
| 3 concurrent workers | Balance speed vs GitHub API rate limits | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after initialization*
