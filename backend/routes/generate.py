"""
/generate routes.

These are intentionally thin — all logic lives in the orchestrator.
Routes handle HTTP concerns only: request validation, response shaping, HTTP errors.
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException
from backend.models.schemas import GenerateRequest, GenerateResponse
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.sandbox.executor import record_pre_runtime_failure
from backend.sockets.manager import emit_agent_state, emit_generation_failure, emit_terminal_line

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.post("", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Dispatch generation job to the background and immediately return.
    Progress is streamed via WebSockets.
    """
    asyncio.create_task(run_orchestrator_bg(req))
    return GenerateResponse(
        success=True,
        project_id=req.project_id,
        files_written=[]
    )

async def run_orchestrator_bg(req: GenerateRequest):
    try:
        result = await generate_project_async(req)
        if not result.success:
            message = result.error or "Generation failed before runtime launch"
            stage = _classify_generation_failure_stage(message)
            if stage != "runtime":
                await record_pre_runtime_failure(req.project_id, message, stage=stage)
                await emit_generation_failure(
                    req.project_id,
                    message,
                    stage=stage,
                    detail={
                        "files_written": result.files_written,
                        "repair_attempts": result.repair_attempts,
                    },
                )
                await emit_terminal_line(f"[GenerationFailed] stage={stage}: {message}", "stderr", req.project_id)
    except Exception as e:
        logger.exception(f"Background orchestrator failed: {e}")
        try:
            stage = "generation"
            await record_pre_runtime_failure(req.project_id, str(e), stage=stage)
            await emit_generation_failure(req.project_id, str(e), stage=stage)
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"Orchestrator crashed: {e}", "stderr", req.project_id)
        except Exception:
            pass
