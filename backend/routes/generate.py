"""
/generate routes.

These are intentionally thin — all logic lives in the orchestrator.
Routes handle HTTP concerns only: request validation, response shaping, HTTP errors.
"""

import asyncio
import datetime
import logging
import time
import uuid
from fastapi import APIRouter, HTTPException
from backend.core.scanner.run_manifest import (
    mark_current_run,
    read_project_generation_status,
    record_project_generation_status,
)
from backend.models.schemas import GenerateRequest, GenerateResponse
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.sandbox.executor import get_runtime_status, record_pre_runtime_failure
from backend.sockets.manager import emit_agent_state, emit_generation_failure, emit_generation_status, emit_terminal_line
from backend.brain.plan_signature import build_plan_signature
from backend.brain.cbr_engine import retain_case

logger = logging.getLogger(__name__)
router = APIRouter()
_generation_status_by_project: dict[str, dict] = {}


def _runtime_status_is(status: str | None, *expected: str) -> bool:
    normalized = str(status or "").upper()
    return normalized in {item.upper() for item in expected}


def _classify_generation_failure_stage(error: str | None) -> str:
    text = (error or "").lower()
    if "dev server" in text or "preview" in text or "runtime" in text or "health" in text:
        return "runtime"
    if "npm install" in text or "install" in text or "dependency" in text:
        return "install"
    if "build" in text or "typescript" in text or "vite" in text:
        return "build"
    if "validation" in text or "contract" in text or "required file" in text:
        return "validation"
    if "no matching skill" in text or "api error" in text or "parse" in text:
        return "generation"
    return "pre_runtime"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_generation_id() -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"gen_{stamp}_{uuid.uuid4().hex[:6]}"


def _record_generation_status(
    project_id: str,
    generation_id: str | None,
    *,
    status: str,
    phase: str,
    message: str,
    detail: dict | None = None,
    runtime_status: dict | None = None,
) -> dict:
    previous = _generation_status_by_project.get(project_id) or {}
    now = _now_ms()
    snapshot = {
        "project_id": project_id,
        "generation_id": generation_id or previous.get("generation_id"),
        "status": status,
        "phase": phase,
        "message": message,
        "detail": detail or {},
        "created_at": previous.get("created_at") or now,
        "updated_at": now,
        "runtime_run_id": None,
        "runtime_url": None,
        "runtime_port": None,
    }
    if runtime_status:
        snapshot["runtime_run_id"] = runtime_status.get("run_id")
        snapshot["runtime_url"] = runtime_status.get("url")
        snapshot["runtime_port"] = runtime_status.get("port")
    _generation_status_by_project[project_id] = snapshot
    try:
        record_project_generation_status(
            project_id,
            status=status,
            generation_id=snapshot.get("generation_id"),
            error=message if status == "failed" else None,
            detail=detail,
        )
    except Exception:
        logger.exception("Failed to persist generation status for project=%s", project_id)
    return snapshot


def _status_from_persisted(project_id: str) -> dict | None:
    persisted = read_project_generation_status(project_id)
    if not persisted:
        return None

    status = persisted.get("status") or "unknown"
    phase = "generating" if status == "running" else status
    if status == "succeeded":
        phase = "completed"
    elif status == "accepted":
        phase = "accepted"
    elif status == "failed":
        phase = "generation"

    return {
        "project_id": project_id,
        "generation_id": persisted.get("generation_id"),
        "run_id": persisted.get("current_run_id"),
        "active_run_id": persisted.get("active_run_id"),
        "latest_run_id": persisted.get("latest_run_id"),
        "status": status,
        "phase": phase,
        "message": persisted.get("error")
        or (
            "Generation completed."
            if status == "succeeded"
            else "Generation is running."
            if status == "running"
            else "Generation request accepted."
            if status == "accepted"
            else "Generation failed."
            if status == "failed"
            else "No generation known for this project."
        ),
        "detail": persisted.get("detail") or {},
        "created_at": persisted.get("created_at"),
        "updated_at": persisted.get("updatedAt") or persisted.get("updated_at"),
        "runtime_run_id": None,
        "runtime_url": None,
        "runtime_port": None,
    }


async def _record_and_emit_generation_status(
    project_id: str,
    generation_id: str | None,
    *,
    status: str,
    phase: str,
    message: str,
    detail: dict | None = None,
    runtime_status: dict | None = None,
) -> dict:
    snapshot = _record_generation_status(
        project_id,
        generation_id,
        status=status,
        phase=phase,
        message=message,
        detail=detail,
        runtime_status=runtime_status,
    )
    await emit_generation_status(snapshot)
    return snapshot


async def mark_latest_generation_runtime_failed(project_id: str, runtime_status: dict) -> dict | None:
    snapshot = _generation_status_by_project.get(project_id)
    run_id = runtime_status.get("run_id")
    if not snapshot or not run_id:
        return None
    if snapshot.get("runtime_run_id") != run_id:
        return None
    if snapshot.get("status") == "failed" and snapshot.get("phase") == "runtime_failed":
        return snapshot

    try:
        mark_current_run(
            project_id,
            status="failed",
            generation_id=snapshot.get("generation_id"),
            error=runtime_status.get("error") or "Runtime failed after generation completed.",
            detail=snapshot.get("detail") or {},
        )
    except Exception:
        logger.exception("Failed to persist runtime failure for project=%s", project_id)

    return await _record_and_emit_generation_status(
        project_id,
        snapshot.get("generation_id"),
        status="failed",
        phase="runtime_failed",
        message=runtime_status.get("error") or "Runtime failed after generation completed.",
        detail=snapshot.get("detail") or {},
        runtime_status=runtime_status,
    )


@router.get("/status/{project_id}")
async def generation_status(project_id: str) -> dict:
    status = _generation_status_by_project.get(project_id)
    if status:
        snapshot = dict(status)
        runtime_status = get_runtime_status(project_id)
        if snapshot.get("runtime_run_id") and runtime_status.get("run_id") == snapshot.get("runtime_run_id"):
            runtime_state = runtime_status.get("status")
            snapshot["runtime_port"] = runtime_status.get("port") if _runtime_status_is(runtime_state, "RUNNING") else None
            snapshot["runtime_url"] = runtime_status.get("url") if _runtime_status_is(runtime_state, "RUNNING") else None
            if _runtime_status_is(runtime_state, "RUNNING"):
                snapshot["phase"] = "runtime_ready"
                snapshot["message"] = "Generation completed and runtime is ready."
            elif _runtime_status_is(runtime_state, "FAILED", "CRASHED"):
                snapshot["status"] = "failed"
                snapshot["phase"] = "runtime_failed"
                snapshot["message"] = runtime_status.get("error") or "Runtime failed after generation completed."
            elif _runtime_status_is(runtime_state, "STOPPED"):
                snapshot["phase"] = "completed"
                snapshot["message"] = "Generation completed; runtime is stopped."
        return snapshot
    persisted = _status_from_persisted(project_id)
    if persisted:
        return persisted
    return {
        "project_id": project_id,
        "generation_id": None,
        "status": "unknown",
        "phase": "none",
        "message": "No generation known for this project.",
        "detail": {},
        "created_at": None,
        "updated_at": None,
        "runtime_run_id": None,
        "runtime_url": None,
        "runtime_port": None,
    }


@router.post("", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Dispatch generation job to the background and immediately return.
    Progress is streamed via WebSockets.
    """
    generation_id = _new_generation_id()
    status_endpoint = f"/generate/status/{req.project_id}"
    _record_generation_status(
        req.project_id,
        generation_id,
        status="accepted",
        phase="accepted",
        message="Generation request accepted and running in the background.",
    )
    asyncio.create_task(run_orchestrator_bg(req, generation_id))
    return GenerateResponse(
        success=True,
        project_id=req.project_id,
        files_written=[],
        accepted=True,
        status="accepted",
        generation_id=generation_id,
        status_endpoint=status_endpoint,
        message="Generation request accepted and running in the background.",
    )

async def run_orchestrator_bg(req: GenerateRequest, generation_id: str | None = None):
    try:
        await _record_and_emit_generation_status(
            req.project_id,
            generation_id,
            status="generating",
            phase="generating",
            message="Generation is running.",
        )
        result = await generate_project_async(req, generation_id=generation_id)
        if not result.success:
            message = result.error or "Generation failed before runtime launch"
            stage = _classify_generation_failure_stage(message)
            
            try:
                from backend.core.reliability import ReliabilityTracker
                ReliabilityTracker.record_event("failure", {"stage": stage, "error": message})
            except Exception:
                pass

            try:
                sig = build_plan_signature(req.prompt)
                from backend.brain.cbr_engine import retain_failure
                retain_failure(req.prompt, sig, message)
            except Exception:
                logger.exception("Failed to retain failed generation as case")

            detail = {
                "files_written": result.files_written,
                "repair_attempts": result.repair_attempts,
            }
            try:
                mark_current_run(
                    req.project_id,
                    status="failed",
                    generation_id=generation_id,
                    prompt=req.prompt,
                    error=message,
                    detail=detail,
                )
            except Exception:
                logger.exception("Failed to persist failed run manifest for project=%s", req.project_id)
            if stage == "runtime":
                runtime_status = get_runtime_status(req.project_id)
                await _record_and_emit_generation_status(
                    req.project_id,
                    generation_id,
                    status="failed",
                    phase="runtime_failed",
                    message=message,
                    detail=detail,
                    runtime_status=runtime_status,
                )
            else:
                await record_pre_runtime_failure(req.project_id, message, stage=stage)
                runtime_status = get_runtime_status(req.project_id)
                await _record_and_emit_generation_status(
                    req.project_id,
                    generation_id,
                    status="failed",
                    phase=stage,
                    message=message,
                    detail=detail,
                    runtime_status=runtime_status,
                )
                await emit_generation_failure(
                    req.project_id,
                    message,
                    stage=stage,
                    detail=detail,
                )
                await emit_terminal_line(f"[GenerationFailed] stage={stage}: {message}", "stderr", req.project_id)
            return

        runtime_status = get_runtime_status(req.project_id)
        runtime_running = _runtime_status_is(runtime_status.get("status"), "RUNNING")
        detail = {
            "files_written": result.files_written,
            "repair_attempts": result.repair_attempts,
        }
        try:
            mark_current_run(
                req.project_id,
                status="succeeded",
                generation_id=generation_id,
                prompt=req.prompt,
                detail=detail,
            )
        except Exception:
            logger.exception("Failed to persist successful run manifest for project=%s", req.project_id)

        # Learn from this successful case
        try:
            sig = build_plan_signature(req.prompt)
            retain_case(req.prompt, sig, detail)
        except Exception:
            logger.exception("Failed to retain successful generation as case")

        await _record_and_emit_generation_status(
            req.project_id,
            generation_id,
            status="succeeded",
            phase="runtime_ready" if runtime_running else "completed",
            message="Generation completed and runtime is ready." if runtime_running else "Generation completed.",
            detail=detail,
            runtime_status=runtime_status,
        )
    except Exception as e:
        logger.exception(f"Background orchestrator failed: {e}")
        try:
            from backend.core.reliability import ReliabilityTracker
            ReliabilityTracker.record_event("failure", {"stage": "orchestrator_crash", "error": str(e)})
        except Exception:
            pass
        try:
            sig = build_plan_signature(req.prompt)
            from backend.brain.cbr_engine import retain_failure
            retain_failure(req.prompt, sig, str(e))
        except Exception:
            pass
        try:
            stage = "generation"
            await record_pre_runtime_failure(req.project_id, str(e), stage=stage)
            runtime_status = get_runtime_status(req.project_id)
            try:
                mark_current_run(
                    req.project_id,
                    status="failed",
                    generation_id=generation_id,
                    prompt=req.prompt,
                    error=str(e),
                )
            except Exception:
                logger.exception("Failed to persist crashed run manifest for project=%s", req.project_id)
            await _record_and_emit_generation_status(
                req.project_id,
                generation_id,
                status="failed",
                phase=stage,
                message=str(e),
                runtime_status=runtime_status,
            )
            await emit_generation_failure(req.project_id, str(e), stage=stage)
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"Orchestrator crashed: {e}", "stderr", req.project_id)
        except Exception:
            pass
