# Architecture Research -- AI GitHub Triage Agent

## Component Boundaries

The system decomposes into six loosely-coupled components, each with a single responsibility:

| Component | Responsibility | Technology Candidates |
|-----------|---------------|----------------------|
| **Webhook Ingress** | Receives, verifies, and normalizes GitHub webhook payloads; enforces HMAC signature validation | FastAPI / Express.js + Hookdeck (edge gateway) |
| **Event Router** | Dispatches events to the appropriate processing pipeline based on event type (issues, pull_request, etc.) | In-memory router or message queue (Redis Streams, RabbitMQ) |
| **AI Processing Engine** | Runs the multi-step LLM workflow: classify, label, score, suggest assignees | LangGraph (Python) or custom state machine |
| **Vector Search Service** | Stores and queries embeddings of historical issues/PRs for similarity matching | Pinecone, Weaviate, or pgvector |
| **Action Executor** | Applies labels, assigns users, posts comments, closes duplicates via GitHub API | GitHub REST/GraphQL API client with rate-limit awareness |
| **Dashboard and Audit** | Real-time UI showing triage decisions, approval queues, and structured decision logs | WebSocket + React/Svelte + structured JSON log store |

### Boundary Principles

1. **Webhook Ingress never calls the LLM directly.** It validates, normalizes, and enqueues. This keeps the ingress path fast and stateless.
2. **AI Processing Engine never calls GitHub APIs directly.** It produces structured decisions (JSON); the Action Executor applies them. This separation enables human-in-the-loop gates and audit trails.
3. **Vector Search is a read-only sidecar.** The AI engine queries it; it never writes back during triage. Embedding writes happen in a separate indexing pipeline.

## Data Flow

### Primary Pipeline (Happy Path)

```
GitHub --[signed webhook]--> Webhook Ingress
                                |
                                v
                         [HMAC verify]
                                |
                                v
                         Event Router --> [enqueue to queue]
                                              |
                                              v
                                    AI Processing Engine
                                    +---------------------+
                                    |  1. Parse and sanitize |
                                    |  2. Embed title+body |
                                    |  3. Vector similarity|
                                    |  4. Classify intent  |
                                    |  5. Score priority   |
                                    |  6. Suggest assignee |
                                    |  7. Check duplicates |
                                    +---------------------+
                                              |
                                              v
                                    [confidence check]
                                    +---------+---------+
                                    |  high   |  low    |
                                    v         v         v
                              Action     HITL       Log
                              Executor   Queue      and skip
                                    |
                                    v
                          [apply labels, assign, comment]
                                    |
                                    v
                          Structured Audit Log
```

### Event Types and Routing

| GitHub Event | Trigger Condition | Pipeline |
|-------------|------------------|----------|
| issues.opened | New issue | Full triage (classify, label, assign, duplicate check) |
| issues.edited | Issue body/title changed | Re-triage if significant change |
| pull_request.opened | New PR | Label by file paths, suggest reviewers |
| pull_request.labeled | Label added | Trigger secondary workflows |
| issue_comment.created | Comment on issue | Sentiment/urgency re-evaluation |
## Suggested Build Order

### Phase 1: Foundation (Week 1-2)
- **Webhook receiver** with HMAC verification and CloudEvents normalization
- **Idempotency layer** using X-GitHub-Delivery header as dedup key
- **Structured logging** pipeline (JSON logs with correlation IDs)
- **Basic LLM classifier** that outputs labels from a fixed allowlist

### Phase 2: Intelligence (Week 3-4)
- **Vector similarity search** -- embed historical issues, query on new issues
- **Duplicate detection** using cosine similarity threshold
- **Priority scoring** based on keywords, author history, and label patterns
- **Assignee suggestion** based on code ownership and past activity

### Phase 3: Safety and Control (Week 5-6)
- **Human-in-the-loop approval gates** for low-confidence decisions
- **Confidence thresholding** -- auto-apply only high-confidence actions
- **LangGraph state machine** for multi-step workflows with retry loops
- **Rate limit management** with token bucket and exponential backoff

### Phase 4: Observability (Week 7-8)
- **Real-time dashboard** with WebSocket event broadcasting
- **Decision audit trail** -- every AI action logged with reasoning, confidence, and timestamp
- **Metrics and alerting** -- accuracy, latency, error rates
- **Demo hardening** -- canned scenarios, fallback modes, offline replay

## Key Patterns

### 1. Webhook to Async Processing to LLM to Action Pipeline

This is the canonical event-driven pattern for AI triage systems:

- **Webhook Ingress** is stateless and fast: verify HMAC signature, validate payload schema, extract the X-GitHub-Delivery idempotency key, and push to a durable queue. Never call the LLM in the webhook handler -- it blocks the response and risks GitHub retrying.
- **Message Queue** provides decoupling. Redis Streams or RabbitMQ are lightweight choices; Kafka is overkill for most triage workloads. The queue enables backpressure: if the LLM API is slow, events accumulate rather than timing out.
- **Worker Processes** pull from the queue, run the LLM pipeline, and emit structured decisions. Workers should be horizontally scalable -- each worker is stateless and processes one event at a time.
- **Action Executor** is a separate component that receives decisions and applies them via GitHub API. This separation is critical: it enables the human-in-the-loop gate (intercept decisions before execution) and the audit trail (log decisions before and after execution).

Real-world reference: The Knative event-driven AI triage demo (Red Hat, 2026) uses CloudEvents + declarative triggers to route messages through autonomous agents (Intake to Structure to Guardian to Router) with no direct coupling between agents. Each agent is a simple HTTP service that receives a POST and returns a CloudEvent in the response headers.

Production reference: Hookdeck + Trigger.dev + Claude (2026) demonstrates a production-ready pattern where Hookdeck handles webhook ingress (HMAC verification, payload transformation, retries, observability) and Trigger.dev handles durable task execution (typed payloads, automatic retries, fan-out, run tracing). The key insight: route events at the edge (Hookdeck header filters) rather than in application code, giving per-event-type observability and independent retry policies.
### 2. State Machine Design for Multi-Step AI Workflows (LangGraph Patterns)

LangGraph models the triage workflow as a **directed graph of functions sharing a typed state object**. This is the right abstraction because triage is inherently non-linear:

```python
class TriageState(TypedDict):
    issue_id: str
    title: str
    body: str
    sanitized_body: str          # After injection sanitization
    embedding: list[float] | None
    similar_issues: list[dict]   # From vector search
    proposed_labels: list[str]
    proposed_priority: str | None
    proposed_assignee: str | None
    confidence: float            # 0.0 - 1.0
    duplicate_of: str | None
    human_decision: str | None   # approved | rejected | modified
    audit_log: list[dict]        # Structured decision trace
    retry_count: int
```

**Key LangGraph patterns to use:**

- **Conditional edges** for routing: after classification, route to duplicate_check, label_assignment, or human_review based on confidence score.
- **Retry loops with counters**: if the LLM call fails, loop back up to 3 times with exponential backoff before escalating to manual review.
- **Parallel fan-out** using Send: run vector similarity search and LLM classification concurrently, then merge results in a synthesize node.
- **interrupt() for HITL gates**: pause the graph at the approval node, surface the proposed actions to a dashboard, and resume with Command(resume=approved) or Command(resume=rejected: reason).
- **Checkpointing with PostgresSaver**: persist state at every node so paused runs survive server restarts. Use thread_id (mapped to X-GitHub-Delivery) as the durable key.
- **Subgraphs for composability**: build a duplicate_detection subgraph and a label_classification subgraph, then compose them in the main triage graph.

**Production rules from LangGraph best practices:**
- One LLM call per node -- split nodes that do too much
- Router functions are pure functions -- test them in isolation
- Always pair loops with a counter or time limit in state
- Use Annotated reducers for fields multiple nodes write to
- MemorySaver is for development only; use PostgresSaver in production
### 3. Vector Search Integration Patterns for Similarity Matching

Vector search serves two purposes in triage: **duplicate detection** and **label suggestion by analogy**.

**Embedding Pipeline:**
- Use a dedicated embedding model (e.g., text-embedding-3-small at 1536 dims, or nomic-embed-text at 768 dims). **Critical**: the embedding dimension must match the vector index dimension exactly. Mismatches are the #1 cause of silent failures in vector search systems.
- Embed the concatenation of title + body for new issues. For historical issues, pre-compute embeddings in a batch indexing job.
- Store metadata alongside vectors: issue_number, labels, state, created_at, repository. This enables hybrid search (semantic + metadata filtering).

**Query Patterns:**
- **Duplicate detection**: query top-K nearest neighbors (K=5-10). If the top result has cosine similarity > 0.85 AND shares at least one label, flag as potential duplicate.
- **Label suggestion**: query top-K, then aggregate labels from similar issues using weighted voting (weight = similarity score).
- **Hybrid filtering**: combine semantic search with metadata filters (e.g., only search within state:open issues, or within specific label categories).

**Dimension mismatch prevention:**
- Declare the embedding dimension as a single source of truth (environment variable or config file).
- Validate at startup: generate a test embedding and verify its length matches the index dimension.
- Log the embedding model name and version alongside each vector for traceability.
- If switching embedding models, create a new index rather than modifying the existing one. Pinecone and other managed services do not support changing index dimensions after creation.

### 4. Human-in-the-Loop Approval Gateway Patterns

Not all AI decisions should execute autonomously. The HITL pattern creates a safety net:

**Confidence-based routing:**
- **High confidence (> 0.85)**: auto-apply labels and assignments. Log the decision.
- **Medium confidence (0.60 - 0.85)**: propose actions, require human approval within a time window (e.g., 24 hours). If no response, escalate to manual triage.
- **Low confidence (< 0.60)**: skip automation entirely, route to manual review queue.

**Approval gate implementation (LangGraph interrupt() pattern):**
1. The triage graph reaches the approval_gate node.
2. interrupt() pauses execution and surfaces a payload containing: proposed labels, proposed assignee, confidence score, similar issues, and reasoning summary.
3. The dashboard renders this payload with Approve, Reject, and Modify buttons.
4. The human decision is passed back via Command(resume=decision).
5. The graph resumes: if approved, the Action Executor applies changes; if rejected, the event is logged and skipped.

**Timeout policy:** Paused runs consume storage. A background job should reject runs older than the SLA (e.g., 24 hours) by calling graph.invoke(Command(resume=rejected: approval timeout)).

**Production HITL rules:**
- Make thread_id durable -- write it to the database immediately
- Use PostgresSaver, not MemorySaver, in multi-worker deployments
- Surface everything the reviewer needs: plan, scope, estimated impact, context links
- Reserve HITL for irreversible actions (closing issues, assigning to specific engineers)
- For two-person sign-off, use Send() to fan out to two approval nodes and merge with a join node
### 5. Real-Time Dashboard Architecture (WebSocket Event Broadcasting)

The dashboard provides live visibility into triage operations:

**Architecture:**
```
Action Executor --> [publish event to Redis Pub/Sub]
                              |
                    WebSocket Server (subscribes)
                              |
                    [broadcast to connected clients]
                              |
                    Browser clients (React/Svelte)
```

**Event types to broadcast:**
- triage_started -- issue received, processing begun
- triage_completed -- decision made (with labels, confidence, reasoning)
- action_applied -- GitHub API call succeeded
- action_failed -- GitHub API call failed (with error details)
- human_review_needed -- low-confidence decision pending approval
- human_review_resolved -- human approved/rejected

**WebSocket design:**
- Use a lightweight server (FastAPI WebSocket, or Socket.IO) that subscribes to a Redis Pub/Sub channel.
- Each event includes a correlation_id (matching the X-GitHub-Delivery header) so the frontend can trace the full lifecycle.
- Implement reconnection with exponential backoff on the client side.
- For scale, use Redis Pub/Sub as the event bus so multiple WebSocket server instances can broadcast to all connected clients.

**Dashboard views:**
- **Live feed**: scrolling list of triage events with status indicators
- **Approval queue**: pending human review items with approve/reject actions
- **Accuracy metrics**: rolling accuracy rate, false positive rate, average latency
- **Decision explorer**: searchable history of all AI decisions with reasoning

### 6. Structured Logging and Audit Trail Patterns for AI Decisions

Every AI decision must be traceable. The audit trail serves three purposes: debugging, compliance, and continuous improvement.

**Decision Trace Protocol (5-layer framework):**

| Layer | What to Log | Example |
|-------|------------|---------|
| **Decision log** | The final decision and confidence | action: add_label, label: bug, confidence: 0.92 |
| **Tool invocation log** | Each LLM call with input/output tokens | model: gpt-4o-mini, input_tokens: 1200, output_tokens: 85, cost_usd: 0.003 |
| **Reasoning log** | The LLM structured reasoning | reasoning: Issue mentions crash on startup and includes stack trace |
| **Context log** | What context was provided to the LLM | similar_issues: [#142, #89], repository_labels: [bug, feature, docs] |
| **Inter-agent log** | Communication between sub-agents | from: classifier, to: duplicate_checker, payload: {...} |

**Storage strategy:**
- Write audit logs to a structured log file (JSON Lines) for immediate debugging.
- Mirror to a database (PostgreSQL) for querying and dashboard display.
- Retain for a configurable period (e.g., 90 days) with automatic archival.
- Never log raw issue body content in audit trails if it may contain sensitive data; log a hash or truncated preview instead.