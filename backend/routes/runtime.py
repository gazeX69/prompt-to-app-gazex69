"""
Runtime lifecycle routes.

Thin HTTP surface over the existing sandbox runtime registry.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.routes.generate import mark_latest_generation_runtime_failed
from backend.agent.tools import _safe_project_path
from backend.core.scanner.workspace_scanner import get_latest_run_id
from backend.runtime_contract import RuntimeErrorCode
from backend.sandbox.executor import (
    get_runtime_status,
    get_runtime_status_for_readback,
    run_dev_server_array_async,
    stop_runtime,
)
from backend.sockets.manager import emit_agent_state, emit_runtime_error, emit_terminal_line

from typing import Optional

router = APIRouter()


class RuntimeStartRequest(BaseModel):
    run_id: str | None = None
    restart: bool = False


@router.get("")
async def list_runtimes() -> dict:
    return get_runtime_status()


@router.get("/{project_id}")
async def runtime_status(project_id: str) -> dict:
    status, invalidated = await get_runtime_status_for_readback(project_id)
    if invalidated:
        await mark_latest_generation_runtime_failed(project_id, status)
    return status


@router.post("/{project_id}/start")
async def start_project_runtime(project_id: str, req: RuntimeStartRequest | None = None) -> dict:
    body = req or RuntimeStartRequest()
    current_status = get_runtime_status(project_id)
    if current_status.get("status") == "running" and not body.restart:
        return current_status

    requested_run_id = body.run_id or current_status.get("run_id") or get_latest_run_id(project_id)

    try:
        run_id = _resolve_runtime_run_id(project_id, requested_run_id)
        command, port_pattern = _infer_runtime_command(project_id, run_id)

    except Exception as exc:
        message = str(exc)
        await emit_terminal_line(f"[RuntimeRun] {message}", "stderr", project_id)
        await emit_runtime_error(
            RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
            message,
            project_id=project_id,
            run_id=run_id,
            source="runtime",
        )
        await emit_agent_state("failed", project_id)
        raise HTTPException(status_code=400, detail=message)

    await emit_terminal_line(f"[RuntimeRun] Starting preview for {run_id}", "info", project_id)
    result = await run_dev_server_array_async(project_id, command, port_pattern=port_pattern, run_id=run_id)
    status = get_runtime_status(project_id)
    if not result.success:
        message = result.error or "Runtime failed to start."
        await emit_runtime_error(
            RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
            message,
            project_id=project_id,
            run_id=run_id,
            source="runtime",
        )
        await emit_agent_state("failed", project_id)
        raise HTTPException(status_code=500, detail=message)
    return status


@router.post("/{project_id}/stop")
async def stop_project_runtime(project_id: str) -> dict:
    return await stop_runtime(project_id)

IGNORED_RUNTIME_DISCOVERY_DIRS = {
    "node_modules",
    "dist",
    ".git",
    ".trash",
    ".orchestration",
    "__pycache__",
}


def _has_supported_runtime_entrypoint(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False

    if (path / "package.json").is_file():
        return True

    if (path / "index.php").is_file():
        return True

    return False


def _find_latest_runnable_run_id(project_root: Path) -> Optional[str]:
    if not project_root.exists() or not project_root.is_dir():
        return None

    candidates: list[Path] = []

    for child in project_root.iterdir():
        if not child.is_dir():
            continue

        if child.name in IGNORED_RUNTIME_DISCOVERY_DIRS:
            continue

        if child.name.startswith("."):
            continue

        if child.name != "latest" and not child.name.startswith("run_"):
            continue

        if _has_supported_runtime_entrypoint(child):
            candidates.append(child)

    if not candidates:
        return None

    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    return latest.name


def _resolve_runtime_run_id(project_id: str, requested_run_id: str | None = None) -> str:
    if requested_run_id:
        requested_path = _safe_project_path(project_id, requested_run_id)
        if _has_supported_runtime_entrypoint(requested_path):
            return requested_run_id

    project_root = _safe_project_path(project_id, None)

    latest_path = project_root / "latest"
    if _has_supported_runtime_entrypoint(latest_path):
        return "latest"

    discovered_run_id = _find_latest_runnable_run_id(project_root)
    if discovered_run_id:
        return discovered_run_id

    raise FileNotFoundError("No runnable generated run found for this project.")

def _infer_runtime_command(project_id: str, run_id: str) -> tuple[list[str], str | None]:
    run_path = _safe_project_path(project_id, run_id)
    if not run_path.exists() or not run_path.is_dir():
        raise FileNotFoundError("Generated run folder not found.")

    package_json = run_path / "package.json"
    if package_json.exists():
        data = _read_json(package_json)
        scripts = data.get("scripts") if isinstance(data, dict) else {}
        if not isinstance(scripts, dict) or "dev" not in scripts:
            raise ValueError("package.json does not define a dev script.")
        deps = {
            **(data.get("dependencies") if isinstance(data.get("dependencies"), dict) else {}),
            **(data.get("devDependencies") if isinstance(data.get("devDependencies"), dict) else {}),
        }
        if "vite" in deps:
            return ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "{port}"], r"http://(?:localhost|127\.0\.0\.1):(\d+)"
        return ["npm", "run", "dev"], r"http://(?:localhost|127\.0\.0\.1):(\d+)|listening|started"

    if (run_path / "index.php").exists():
        return ["php", "-S", "127.0.0.1:{port}"], r"http://(?:localhost|127\.0\.0\.1):(\d+)|started|Development Server|Listening"

    raise ValueError("No supported runtime entry point found for this run.")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid package.json: {exc}") from exc
