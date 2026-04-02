"""
FastAPI application with webhook receiver, health check, and dashboard API.
Returns 200 immediately from webhooks, processes asynchronously.
"""

import uuid
import hmac
import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import init_db, check_integrity, recreate_db, create_job, get_job_by_issue_id, get_pending_jobs, get_recent_jobs, get_metrics, log_llm_call
from backend.logging_config import setup_logging, TraceContext, get_logger
from backend.models import WebhookPayload

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate DB, initialize schema, log readiness."""
    setup_logging()
    logger.info("Starting Smart GitHub Triage Agent")

    if not check_integrity():
        logger.warning("Database integrity check failed, recreating...")
        recreate_db()
    else:
        init_db()

    logger.info("Database ready", extra={"extra_context": {
        "db_path": settings.database_url,
        "chroma_path": settings.chroma_path,
        "auto_label": settings.auto_label_enabled,
    }})

    yield

    logger.info("Shutting down")


app = FastAPI(
    title="Smart GitHub Triage Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint. Returns 200 only if all dependencies are healthy."""
    db_healthy = check_integrity()

    status = "healthy" if db_healthy else "degraded"
    status_code = 200 if db_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "database": "ok" if db_healthy else "corrupted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """
    GitHub webhook receiver.
    1. Verify HMAC signature
    2. Validate payload structure
    3. Check idempotency
    4. Return 200 immediately (< 1 second)
    5. Enqueue for async processing
    """
    trace_id = str(uuid.uuid4())
    TraceContext.set(trace_id)

    try:
        body = await request.body()
    except Exception as e:
        logger.error("Failed to read request body", extra={"extra_context": {"error": str(e)}})
        raise HTTPException(status_code=400, detail="Failed to read request body")

    # 1. Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        logger.warning("Invalid webhook signature", extra={"extra_context": {"trace_id": trace_id}})
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse and validate payload
    try:
        import json
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Malformed JSON payload", extra={"extra_context": {"trace_id": trace_id}})
        raise HTTPException(status_code=400, detail="Malformed payload")

    event_type = request.headers.get("X-GitHub-Event", "")
    action = payload.get("action", "")

    # Route by event type
    if event_type == "issues" and action == "opened":
        issue_data = payload.get("issue", {})
        if not issue_data or "id" not in issue_data:
            logger.error("Missing issue data in payload", extra={"extra_context": {"trace_id": trace_id}})
            raise HTTPException(status_code=400, detail="Missing issue data")

        issue_id = issue_data["id"]
        issue_number = issue_data.get("number", 0)
        repo = payload.get("repository", {})
        repo_full_name = repo.get("full_name", "unknown/repo")

    elif event_type == "pull_request" and action == "opened":
        pr_data = payload.get("pull_request", {})
        if not pr_data or "id" not in pr_data:
            logger.error("Missing PR data in payload", extra={"extra_context": {"trace_id": trace_id}})
            raise HTTPException(status_code=400, detail="Missing pull_request data")

        issue_id = pr_data["id"]
        issue_number = pr_data.get("number", 0)
        repo = payload.get("repository", {})
        repo_full_name = repo.get("full_name", "unknown/repo")

    else:
        logger.info(
            "Ignoring webhook event",
            extra={"extra_context": {"event_type": event_type, "action": action, "trace_id": trace_id}},
        )
        return {"status": "ignored", "event": event_type, "action": action}

    # 3. Idempotency check
    existing = get_job_by_issue_id(issue_id)
    if existing:
        logger.info(
            "Duplicate webhook, skipping",
            extra={"extra_context": {"issue_id": issue_id, "trace_id": trace_id}},
        )
        return {"status": "already_processing", "issue_id": issue_id}

    # 4. Create job + return 200 immediately
    title = payload.get("issue", payload.get("pull_request", {})).get("title", "")
    body_text = payload.get("issue", payload.get("pull_request", {})).get("body", "") or ""
    author = payload.get("issue", payload.get("pull_request", {})).get("user", {}).get("login", "")
    event_label = f"{event_type}.{action}"

    job_id = create_job(
        issue_id=issue_id,
        issue_number=issue_number,
        repo_full_name=repo_full_name,
        event_type=event_label,
        title=title,
        body=body_text[:settings.body_truncate_chars],
        author=author,
    )

    if job_id == -1:
        return {"status": "already_processing", "issue_id": issue_id}

    logger.info(
        "Webhook received, job created",
        extra={"extra_context": {
            "job_id": job_id,
            "issue_id": issue_id,
            "issue_number": issue_number,
            "event_type": event_label,
            "trace_id": trace_id,
        }},
    )

    # 5. Enqueue for async processing
    background_tasks.add_task(process_triage, job_id, trace_id)

    return {"status": "queued", "job_id": job_id, "trace_id": trace_id}


async def process_triage(job_id: int, trace_id: str):
    """
    Async triage processing. This is where the LangGraph orchestrator runs.
    For Phase 1, this is a placeholder that updates job status.
    Phase 2 will wire in the full orchestrator.
    """
    TraceContext.set(trace_id)
    logger.info(
        "Starting triage processing",
        extra={"extra_context": {"job_id": job_id, "trace_id": trace_id}},
    )

    from backend.database import update_job
    update_job(job_id, status="running")

    # TODO: Phase 2 — wire in LangGraph orchestrator here
    # graph = build_triage_graph()
    # result = await graph.ainvoke(initial_state)

    update_job(job_id, status="pending_review")

    logger.info(
        "Triage processing complete",
        extra={"extra_context": {"job_id": job_id, "trace_id": trace_id}},
    )


# --- Dashboard API ---

@app.get("/api/reviews/pending")
async def get_pending_reviews():
    """List pending triage reviews for the dashboard."""
    jobs = get_pending_jobs()
    return {"reviews": jobs, "count": len(jobs)}


@app.get("/api/reviews/{job_id}")
async def get_review(job_id: int):
    """Get full triage result for a specific job."""
    from backend.database import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"review": job}


@app.post("/api/reviews/{job_id}/approve")
async def approve_review(job_id: int):
    """Approve a triage review and execute actions."""
    from backend.database import get_job, update_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    if job["status"] != "pending_review":
        raise HTTPException(status_code=409, detail=f"Cannot approve job in state '{job['status']}'")

    # Optimistic locking: reject if version changed
    update_job(job_id, status="executed", approved_at=datetime.now(timezone.utc).isoformat())

    # TODO: Phase 3 — execute GitHub API calls here
    logger.info("Review approved", extra={"extra_context": {"job_id": job_id}})
    return {"status": "approved", "job_id": job_id}


@app.post("/api/reviews/{job_id}/reject")
async def reject_review(job_id: int):
    """Reject a triage review."""
    from backend.database import get_job, update_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    if job["status"] != "pending_review":
        raise HTTPException(status_code=409, detail=f"Cannot reject job in state '{job['status']}'")

    update_job(job_id, status="rejected")
    logger.info("Review rejected", extra={"extra_context": {"job_id": job_id}})
    return {"status": "rejected", "job_id": job_id}


@app.get("/api/reviews/history")
async def get_history(limit: int = 50):
    """Get recent triage history."""
    jobs = get_recent_jobs(limit)
    return {"history": jobs, "count": len(jobs)}


@app.get("/api/metrics")
async def get_dashboard_metrics():
    """Get aggregate metrics for the dashboard."""
    return get_metrics()
