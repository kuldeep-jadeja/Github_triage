"""
FastAPI application with webhook receiver, health check, dashboard API, and WebSocket.
Returns 200 immediately from webhooks, processes asynchronously.
"""

import uuid
import hmac
import hashlib
import json
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import (
    init_db, check_integrity, recreate_db, create_job, get_job_by_issue_id,
    get_pending_jobs, get_recent_jobs, get_metrics, log_llm_call,
    get_job, update_job,
)
from backend.logging_config import setup_logging, TraceContext, get_logger

logger = get_logger(__name__)


# --- WebSocket Manager ---

class ConnectionManager:
    """Manages WebSocket connections and broadcasts events to all clients."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event: dict):
        """Send an event to all connected clients."""
        message = json.dumps(event)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


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


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time triage progress updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — client sends ping, we respond
            data = await websocket.receive_text()
            # Echo back for keepalive
            await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def broadcast_event(event_type: str, data: dict):
    """Helper to broadcast an event to all WebSocket clients."""
    await manager.broadcast({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **data,
    })


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

    # Broadcast to dashboard
    asyncio.create_task(broadcast_event("triage_started", {
        "job_id": job_id,
        "issue_number": issue_number,
        "title": title,
        "status": "queued",
    }))

    return {"status": "queued", "job_id": job_id, "trace_id": trace_id}


async def process_triage(job_id: int, trace_id: str):
    """
    Async triage processing using the LangGraph orchestrator.
    Runs the full state machine: intake → analyze → search → decide → draft → critique → policy → complete.
    """
    TraceContext.set(trace_id)
    logger.info(
        "Starting triage processing",
        extra={"extra_context": {"job_id": job_id, "trace_id": trace_id}},
    )

    from backend.orchestrator import build_triage_graph
    from backend.models import TriageState
    from backend.github_tools import GitHubTools

    job = get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    update_job(job_id, status="running")
    await broadcast_event("triage_progress", {
        "job_id": job_id,
        "status": "running",
        "step": "Starting analysis...",
    })

    try:
        initial_state = TriageState(
            issue_id=job["issue_id"],
            issue_number=job["issue_number"],
            repo_full_name=job["repo_full_name"],
            event_type=job["event_type"],
            title=job.get("title") or "",
            body=job.get("body") or "",
            author=job.get("author") or "",
            trace_id=trace_id,
        )

        graph = build_triage_graph()
        result = await graph.ainvoke(initial_state)

        status = result.get("status", "pending_review")
        update_job(
            job_id,
            status=status,
            suggested_labels=str(result.get("suggested_labels", [])),
            suggested_priority=result.get("suggested_priority", "P2"),
            confidence=result.get("confidence", 0.0),
            reasoning=result.get("reasoning", ""),
            draft_comment=result.get("draft_comment", ""),
            critique_notes=result.get("critique_notes", ""),
            trace_log=str(result.get("trace_log", [])),
        )

        # If auto-label is applicable, execute immediately
        if status == "auto_labeled":
            tools = GitHubTools(repo_name=job["repo_full_name"])
            labels = result.get("suggested_labels", [])
            if labels:
                tools.apply_labels(job["issue_number"], labels)
            update_job(job_id, executed_at=datetime.now(timezone.utc).isoformat())
            await broadcast_event("triage_complete", {
                "job_id": job_id,
                "status": "auto_labeled",
                "labels": labels,
                "confidence": result.get("confidence", 0.0),
            })
        else:
            await broadcast_event("triage_complete", {
                "job_id": job_id,
                "status": status,
                "confidence": result.get("confidence", 0.0),
            })

        logger.info(
            "Triage processing complete",
            extra={"extra_context": {
                "job_id": job_id,
                "status": status,
                "confidence": result.get("confidence", 0.0),
                "trace_id": trace_id,
            }},
        )

    except Exception as e:
        logger.error(
            f"Triage processing failed: {e}",
            extra={"extra_context": {"job_id": job_id, "trace_id": trace_id}},
        )
        update_job(job_id, status="error", error=str(e))
        await broadcast_event("triage_error", {
            "job_id": job_id,
            "error": str(e),
        })


# --- Dashboard API ---

@app.get("/api/reviews/pending")
async def get_pending_reviews():
    """List pending triage reviews for the dashboard."""
    jobs = get_pending_jobs()
    return {"reviews": jobs, "count": len(jobs)}


@app.get("/api/reviews/{job_id}")
async def get_review(job_id: int):
    """Get full triage result for a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"review": job}


@app.post("/api/reviews/{job_id}/approve")
async def approve_review(job_id: int):
    """Approve a triage review and execute actions on GitHub."""
    from backend.github_tools import GitHubTools

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    if job["status"] not in ("pending_review", "auto_labeled"):
        raise HTTPException(status_code=409, detail=f"Cannot approve job in state '{job['status']}'")

    # Optimistic locking: reject if version changed
    update_job(job_id, status="executed", approved_at=datetime.now(timezone.utc).isoformat())

    # Execute on GitHub
    tools = GitHubTools(repo_name=job["repo_full_name"])

    # Apply labels
    import ast
    try:
        labels = ast.literal_eval(job.get("suggested_labels") or "[]")
    except (ValueError, SyntaxError):
        labels = []

    if labels:
        tools.apply_labels(job["issue_number"], labels)

    # Post comment (use edited draft if available, otherwise original)
    draft = job.get("edited_draft") or job.get("draft_comment") or ""
    if draft:
        tools.post_comment(job["issue_number"], draft)

    update_job(job_id, executed_at=datetime.now(timezone.utc).isoformat())
    await broadcast_event("review_approved", {"job_id": job_id, "issue_number": job["issue_number"]})

    logger.info("Review approved and executed", extra={"extra_context": {"job_id": job_id}})
    return {"status": "approved", "job_id": job_id}


@app.post("/api/reviews/{job_id}/reject")
async def reject_review(job_id: int):
    """Reject a triage review."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    if job["status"] not in ("pending_review", "auto_labeled"):
        raise HTTPException(status_code=409, detail=f"Cannot reject job in state '{job['status']}'")

    update_job(job_id, status="rejected")
    await broadcast_event("review_rejected", {"job_id": job_id})
    logger.info("Review rejected", extra={"extra_context": {"job_id": job_id}})
    return {"status": "rejected", "job_id": job_id}


@app.post("/api/reviews/{job_id}/edit")
async def edit_review(job_id: int, request: Request):
    """Edit a draft comment before approval. Stores the edited version."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    if job["status"] not in ("pending_review", "auto_labeled"):
        raise HTTPException(status_code=409, detail=f"Cannot edit job in state '{job['status']}'")

    body = await request.json()
    edited_draft = body.get("draft_comment", "")
    if not edited_draft:
        raise HTTPException(status_code=400, detail="draft_comment is required")

    original_draft = job.get("draft_comment") or ""
    update_job(job_id, edited_draft=edited_draft)

    logger.info("Draft edited", extra={"extra_context": {"job_id": job_id}})
    return {
        "status": "edited",
        "job_id": job_id,
        "original": original_draft,
        "edited": edited_draft,
    }


@app.post("/api/reviews/{job_id}/undo")
async def undo_auto_label(job_id: int):
    """Undo an auto-labeled triage — removes the labels that were applied."""
    from backend.github_tools import GitHubTools

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Review not found")
    if job["status"] != "auto_labeled":
        raise HTTPException(status_code=409, detail="Can only undo auto-labeled reviews")

    # Remove the labels that were applied
    import ast
    try:
        labels = ast.literal_eval(job.get("suggested_labels") or "[]")
    except (ValueError, SyntaxError):
        labels = []

    if labels:
        tools = GitHubTools(repo_name=job["repo_full_name"])
        try:
            issue = tools.repo.get_issue(job["issue_number"])
            for label in labels:
                issue.remove_from_labels(label)
            logger.info(f"Removed labels {labels} from #{job['issue_number']}")
        except Exception as e:
            logger.error(f"Failed to remove labels: {e}")

    update_job(job_id, status="pending_review")
    await broadcast_event("label_undone", {"job_id": job_id})
    return {"status": "undone", "job_id": job_id}


@app.get("/api/reviews/history")
async def get_history(limit: int = 50):
    """Get recent triage history."""
    jobs = get_recent_jobs(limit)
    return {"history": jobs, "count": len(jobs)}


@app.get("/api/metrics")
async def get_dashboard_metrics():
    """Get aggregate metrics for the dashboard."""
    return get_metrics()
