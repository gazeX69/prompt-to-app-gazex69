"""
Runtime lifecycle routes.

Thin HTTP surface over the existing sandbox runtime registry.
"""

from fastapi import APIRouter

from backend.sandbox.executor import get_runtime_status, stop_runtime

router = APIRouter()


@router.get("")
async def list_runtimes() -> dict:
    return get_runtime_status()


@router.get("/{project_id}")
async def runtime_status(project_id: str) -> dict:
    return get_runtime_status(project_id)


@router.post("/{project_id}/stop")
async def stop_project_runtime(project_id: str) -> dict:
    return await stop_runtime(project_id)
