# Roadmap — Smart GitHub Triage Agent

## M001: Build & Ship MVP

**Goal:** A working AI agent that triages GitHub issues and PRs, presents recommendations to maintainers via a real-time dashboard, and executes approved actions — ready for hackathon demo.

### Phase 1: Foundation — Webhook, Config, Logging, SQLite
**Goal:** Receive webhooks, verify signatures, store state, log everything
**Requirements:** WEBHOOK-01, WEBHOOK-02, WEBHOOK-03, WEBHOOK-04, LOGGING-01, LOGGING-02, LOGGING-03, SECURITY-01
**Success Criteria:**
1. POST /webhook returns 200 in <1s with valid HMAC signature
2. Duplicate webhook deliveries are detected and skipped (idempotency)
3. Both issues.opened and pull_request.opened events are routed correctly
4. JSON structured logs with trace_id appear in stdout for every step
5. SQLite database stores triage jobs with all required fields
6. Prompt injection attempts in issue body are tagged and flagged

### Phase 2: Intelligence — LLM, Vector Search, Policy Engine
**Goal:** Analyze issues, find similar past issues, generate triage decisions with auto-label support
**Requirements:** TRIAGE-01, TRIAGE-02, TRIAGE-03, TRIAGE-04, TRIAGE-05, TRIAGE-06, TRIAGE-07, TRIAGE-08, AUTO-01, AUTO-02, DRAFT-01, DRAFT-02
**Success Criteria:**
1. LLM returns structured output (labels, priority, confidence, reasoning) via Pydantic validation
2. Similar issues found with cosine similarity scores (≥0.88 = duplicate, 0.75-0.87 = related)
3. Non-English issues (ES, ZH, JA, FR, DE) are detected, translated, and triaged
4. Labels are validated against repo's actual label set — no hallucinated labels
5. Auto-label applies at >=0.95 confidence when AUTO_LABEL_ENABLED=true
6. PR diffs are extracted, summarized, and reviewer suggestions made
7. Issue template validation flags missing sections
8. Draft comments are professional, under 200 words, include similar issue links

### Phase 3: Dashboard & Execution — React UI, WebSocket, GitHub Actions
**Goal:** Real-time dashboard where maintainers approve/reject triage decisions, actions executed on GitHub
**Requirements:** DASHBOARD-01, DASHBOARD-02, DASHBOARD-03, DASHBOARD-04, DASHBOARD-05, DASHBOARD-06, EXECUTE-01, EXECUTE-02, EXECUTE-03, SECURITY-02, SECURITY-03
**Success Criteria:**
1. Dashboard shows pending triage reviews with color-coded reasoning timeline
2. Approve button applies labels and posts comment on GitHub
3. Reject button marks job rejected with no GitHub action
4. Edit button shows diff between original and edited draft
5. WebSocket pushes live progress updates ("Analyzing...", "Searching...", "Drafting...")
6. Metrics panel shows total triaged, avg confidence, accuracy trend, time-to-triage
7. History page shows filterable audit log of all past decisions
8. Optimistic locking prevents double-click duplicate execution
9. GitHub OAuth restricts dashboard to users with write access

### Phase 4: Testing, Deployment & Demo Prep
**Goal:** All tests passing, Docker deployment working, demo ready
**Requirements:** TEST-01, TEST-02, TEST-03, TEST-04, TEST-05, TEST-06, TEST-07, DEPLOY-01, DEPLOY-02, DEPLOY-03
**Success Criteria:**
1. All unit tests pass for each LangGraph node
2. Webhook idempotency test passes with 100 concurrent duplicates
3. Prompt injection tests pass — no injected instructions followed
4. Multi-language tests pass for all 5 languages
5. E2E test passes: webhook → triage → approve → labels applied + comment posted
6. Docker Compose brings up full stack (backend + dashboard + SQLite + Chroma)
7. Demo repo seeded with 50+ issues, vector DB bootstrapped
8. README documents setup, architecture, and demo strategy

## Phase Dependencies

```
Phase 1 (Foundation)
    │
    ├──► Phase 2 (Intelligence)
    │         │
    │         ├──► Phase 3 (Dashboard & Execution)
    │         │         │
    │         │         └──► Phase 4 (Testing & Deploy)
    │         │
    │         └──► [Parallel: Bootstrap script]
    └──► [Parallel: Docker setup]
```

## Risk Assessment

| Phase | Risk | Mitigation |
|---|---|---|
| Phase 1 | Low — standard webhook pattern | Well-documented, FastAPI handles async |
| Phase 2 | Medium — LLM reliability | Structured output + fallback + retry |
| Phase 3 | Medium — WebSocket complexity | Server-Sent Events as fallback |
| Phase 4 | Low — standard testing/deploy | Docker Compose simplifies deployment |
