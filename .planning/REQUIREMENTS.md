# Requirements — Smart GitHub Triage Agent

## v1 Requirements

### Webhook & Intake
- [ ] **WEBHOOK-01**: Receive and verify GitHub webhook signatures (HMAC-SHA256)
- [ ] **WEBHOOK-02**: Handle issues.opened events with idempotency check
- [ ] **WEBHOOK-03**: Handle pull_request.opened events with idempotency check
- [ ] **WEBHOOK-04**: Return 200 response within 1 second, process asynchronously

### Triage Intelligence
- [ ] **TRIAGE-01**: Extract structured info from issue/PR content (title, body, error patterns, platform)
- [ ] **TRIAGE-02**: Detect language and translate non-English content (ES, ZH, JA, FR, DE)
- [ ] **TRIAGE-03**: Search similar past issues via vector embeddings (cosine similarity)
- [ ] **TRIAGE-04**: Suggest labels from repo's existing label set only (no hallucinated labels)
- [ ] **TRIAGE-05**: Assign priority (P0-P3) with 2-3 sentence reasoning
- [ ] **TRIAGE-06**: Detect missing information and generate specific clarifying questions
- [ ] **TRIAGE-07**: Validate against .github/ISSUE_TEMPLATE/ files, flag missing sections
- [ ] **TRIAGE-08**: Extract PR diff summary (file list + 2000 char diff) and suggest reviewers

### Automation
- [ ] **AUTO-01**: Auto-apply labels when confidence >= 0.95 (env-toggleable via AUTO_LABEL_ENABLED)
- [ ] **AUTO-02**: Policy engine blocks destructive actions (close, lock, transfer)

### Draft & Response
- [ ] **DRAFT-01**: Generate friendly, professional draft comments in GitHub-flavored markdown
- [ ] **DRAFT-02**: Include similar issue links, clarifying questions, label/priority rationale

### Dashboard
- [ ] **DASHBOARD-01**: Show pending triage reviews with agent reasoning (color-coded timeline)
- [ ] **DASHBOARD-02**: Allow approve/edit/reject of triage decisions
- [ ] **DASHBOARD-03**: Real-time updates via WebSocket during triage progress
- [ ] **DASHBOARD-04**: Show metrics panel (total triaged, avg confidence, accuracy, time-to-triage)
- [ ] **DASHBOARD-05**: Show comment edit diff when maintainers modify drafts
- [ ] **DASHBOARD-06**: History/audit log of all past triage decisions with filtering

### Execution
- [ ] **EXECUTE-01**: Apply labels via GitHub API on approval
- [ ] **EXECUTE-02**: Post comment via GitHub API on approval
- [ ] **EXECUTE-03**: Optimistic locking prevents double-click duplicate execution

### Security
- [ ] **SECURITY-01**: Prompt injection defense via `<user_input>` and `<reference_data>` tags
- [ ] **SECURITY-02**: GitHub OAuth for dashboard with write permission check
- [ ] **SECURITY-03**: WebSocket authentication via session token

### Logging & Observability
- [ ] **LOGGING-01**: Full audit trail with trace_id propagation through entire flow
- [ ] **LOGGING-02**: JSON structured logging to stdout with trace_id, timestamp, level, event, context
- [ ] **LOGGING-03**: LLM call logging (model, tokens, latency, error) for cost tracking

### Testing
- [ ] **TEST-01**: Unit tests for each LangGraph node
- [ ] **TEST-02**: Webhook idempotency tests (100 concurrent duplicates)
- [ ] **TEST-03**: Prompt injection tests (5+ malicious issue bodies)
- [ ] **TEST-04**: Multi-language tests (5 languages × 3 issues each)
- [ ] **TEST-05**: Edge case tests (empty, image-only, very long, bot-created)
- [ ] **TEST-06**: PR tests (small, large, binary-only, merge conflict)
- [ ] **TEST-07**: 1 E2E flow test (webhook → triage → approve → GitHub)

### Deployment
- [ ] **DEPLOY-01**: Docker + Docker Compose setup
- [ ] **DEPLOY-02**: Demo repo seeding script (50+ issues)
- [ ] **DEPLOY-03**: Documentation (README, setup guide, architecture)

## v2 Requirements (Deferred)
- [ ] Multi-repo support with per-repo configuration
- [ ] Slack/Discord notifications for triage-ready alerts
- [ ] Self-improvement from maintainer feedback
- [ ] Issue edit tracking (issues.edited webhook)
- [ ] Auto-assignment based on maintainer expertise mapping
- [ ] Full mobile-responsive dashboard
- [ ] Keyboard shortcuts for power users

## Out of Scope
- Auto-closing duplicates — too risky, suggest-only is safer
- Permanent autonomous operation — human-in-the-loop always available
- Black-box decisions — full reasoning trace required
- One-size-fits-all labeling — per-repo customization needed

## Traceability

| Requirement | Phase | Status |
|---|---|---|
| WEBHOOK-01 through WEBHOOK-04 | Phase 1 | Pending |
| TRIAGE-01 through TRIAGE-08 | Phase 2 | Pending |
| AUTO-01 through AUTO-02 | Phase 2 | Pending |
| DRAFT-01 through DRAFT-02 | Phase 2 | Pending |
| DASHBOARD-01 through DASHBOARD-06 | Phase 3 | Pending |
| EXECUTE-01 through EXECUTE-03 | Phase 3 | Pending |
| SECURITY-01 through SECURITY-03 | Phase 1-3 | Pending |
| LOGGING-01 through LOGGING-03 | Phase 1 | Pending |
| TEST-01 through TEST-07 | Phase 4 | Pending |
| DEPLOY-01 through DEPLOY-03 | Phase 4 | Pending |
