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
from backend.sockets.manager import emit_agent_state, emit_terminal_line

logger = logging.getLogger(__name__)
router = APIRouter()


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
        await generate_project_async(req)
    except Exception as e:
        logger.exception(f"Background orchestrator failed: {e}")
        try:
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"Orchestrator crashed: {e}", "stderr", req.project_id)
        except Exception:
            pass
