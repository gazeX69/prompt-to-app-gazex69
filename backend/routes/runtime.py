"""
Runtime lifecycle routes.

Thin HTTP surface over the existing sandbox runtime registry.
"""

from fastapi import APIRouter

from backend.routes.generate import mark_latest_generation_runtime_failed
from backend.sandbox.executor import get_runtime_status, get_runtime_status_for_readback, stop_runtime

router = APIRouter()


@router.get("")
async def list_runtimes() -> dict:
    return get_runtime_status()


@router.get("/{project_id}")
async def runtime_status(project_id: str) -> dict:
    status, invalidated = await get_runtime_status_for_readback(project_id)
    if invalidated:
        await mark_latest_generation_runtime_failed(project_id, status)
    return status


@router.post("/{project_id}/stop")
async def stop_project_runtime(project_id: str) -> dict:
    return await stop_runtime(project_id)
