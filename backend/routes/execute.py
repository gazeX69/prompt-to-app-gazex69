"""
/execute routes.

Exposes the sandbox execution engine over HTTP.
Only whitelisted commands are accepted (enforced in sandbox/executor.py).
"""

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ExecuteRequest, ExecuteResponse
from backend.sandbox.executor import stream_command_async

router = APIRouter()


@router.post("", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest) -> ExecuteResponse:
    """
    Run a whitelisted command inside a project workspace.

    Allowed commands: install, build, dev, lint, test
    """
    result = await stream_command_async(req.project_id, req.command)

    if not result.success and result.error and "not allowed" in (result.error or ""):
        raise HTTPException(status_code=400, detail=result.error)

    return result
