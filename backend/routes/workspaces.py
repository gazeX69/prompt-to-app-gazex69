from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.scanner.workspace_scanner import (
    scan_workspaces,
    create_workspace_project,
    update_workspace_project,
    duplicate_workspace_project,
    archive_workspace_project,
    get_workspace_runs,
    get_workspace_tree,
    get_workspace_artifacts,
    get_workspace_artifact_content,
    get_workspace_file_content,
    save_workspace_file_content,
    create_workspace_entry,
    move_workspace_entry,
    delete_workspace_entry,
    extract_workspace_symbols,
    get_workspace_references
)
from backend.core.scanner.patch_grounding import (
    get_workspace_regions,
    get_persisted_patches,
    get_persisted_replays
)
from backend.core.scanner.patch_simulation import get_persisted_simulations
from backend.core.scanner.execution_readiness import get_execution_readiness
from backend.sandbox.executor import get_runtime_status
from backend.memory.project_memory import ProjectMemory
from backend.memory.workspace_awareness import WorkspaceAwareness
from backend.brain.change_scope import ChangeScopeAnalyzer
from backend.reflection.reflection_engine import ReflectionEngine

router = APIRouter()

class WorkspaceFileSaveRequest(BaseModel):
    content: str


class WorkspaceEntryCreateRequest(BaseModel):
    path: str
    type: str
    content: str = ""


class WorkspaceEntryMoveRequest(BaseModel):
    path_id: str
    new_path: str

class WorkspaceCreateRequest(BaseModel):
    name: str
    template: str | None = None


class WorkspaceUpdateRequest(BaseModel):
    name: str


class WorkspaceDuplicateRequest(BaseModel):
    name: str | None = None


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _with_runtime_status(workspace: dict) -> dict:
    runtime_status = get_runtime_status(workspace["id"])
    status = runtime_status.get("status") or workspace.get("status") or "unknown"
    if status == "running":
        runtime_health = "healthy"
    elif status == "failed":
        runtime_health = "degraded"
    else:
        runtime_health = "offline"
    try:
        project_state = ProjectMemory.get_project_state(workspace["id"])
    except Exception:
        project_state = None
    return {
        **workspace,
        "status": status if status in {"running", "failed"} else workspace.get("status", "ready"),
        "runtime_status": runtime_status,
        "runtimeHealth": runtime_health,
        "project_state": project_state,
    }


@router.get("")
def list_workspaces():
    return [_with_runtime_status(ws) for ws in scan_workspaces()]


@router.post("")
def create_workspace(req: WorkspaceCreateRequest):
    try:
        workspace = create_workspace_project(req.name, req.template)
        ProjectMemory.initialize_project(workspace["id"], req.template or "blank")
        return {**workspace, "project_state": ProjectMemory.get_project_state(workspace["id"])}
    except Exception as exc:
        raise _http_error(exc)

@router.get("/{workspace_id}")
def get_workspace(workspace_id: str):
    wses = scan_workspaces()
    for w in wses:
        if w["id"] == workspace_id:
            return _with_runtime_status(w)
    raise HTTPException(status_code=404, detail="Workspace not found")


@router.patch("/{workspace_id}")
def update_workspace(workspace_id: str, req: WorkspaceUpdateRequest):
    try:
        return update_workspace_project(workspace_id, req.name)
    except Exception as exc:
        raise _http_error(exc)


@router.post("/{workspace_id}/duplicate")
def duplicate_workspace(workspace_id: str, req: WorkspaceDuplicateRequest):
    try:
        return duplicate_workspace_project(workspace_id, req.name)
    except Exception as exc:
        raise _http_error(exc)


@router.delete("/{workspace_id}")
def archive_workspace(workspace_id: str):
    runtime_status = get_runtime_status(workspace_id)
    if runtime_status.get("status") not in {None, "unknown", "stopped", "failed"}:
        raise HTTPException(
            status_code=409,
            detail="Stop the active runtime before archiving this project.",
        )
    try:
        return archive_workspace_project(workspace_id)
    except Exception as exc:
        raise _http_error(exc)

@router.get("/{workspace_id}/runs")
def list_workspace_runs(workspace_id: str):
    return get_workspace_runs(workspace_id)

@router.get("/{workspace_id}/repository-tree")
def get_repository_tree(workspace_id: str, run_id: str | None = None):
    return get_workspace_tree(workspace_id, run_id)

@router.get("/{workspace_id}/artifacts")
def list_workspace_artifacts(workspace_id: str, run_id: str | None = None):
    return get_workspace_artifacts(workspace_id, run_id)

@router.get("/{workspace_id}/artifacts/{artifact_id}")
def get_artifact_content(workspace_id: str, artifact_id: str, run_id: str | None = None):
    return get_workspace_artifact_content(workspace_id, artifact_id, run_id)

@router.get("/{workspace_id}/file")
def get_file_content(workspace_id: str, path_id: str, run_id: str | None = None):
    return get_workspace_file_content(workspace_id, path_id, run_id)

@router.put("/{workspace_id}/file")
def save_file_content(
    workspace_id: str,
    req: WorkspaceFileSaveRequest,
    path_id: str,
    run_id: str | None = None,
):
    result = save_workspace_file_content(workspace_id, path_id, req.content, run_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.post("/{workspace_id}/entry")
def create_entry(
    workspace_id: str,
    req: WorkspaceEntryCreateRequest,
    run_id: str | None = None,
):
    result = create_workspace_entry(workspace_id, req.path, req.type, req.content, run_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.patch("/{workspace_id}/entry")
def move_entry(
    workspace_id: str,
    req: WorkspaceEntryMoveRequest,
    run_id: str | None = None,
):
    result = move_workspace_entry(workspace_id, req.path_id, req.new_path, run_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.delete("/{workspace_id}/entry")
def delete_entry(workspace_id: str, path_id: str, run_id: str | None = None):
    result = delete_workspace_entry(workspace_id, path_id, run_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/{workspace_id}/symbols")
def get_symbols(workspace_id: str, run_id: str | None = None, path_id: str | None = None):
    return extract_workspace_symbols(workspace_id, run_id, path_id)

@router.get("/{workspace_id}/references")
def get_references(workspace_id: str, path_id: str, run_id: str | None = None):
    return get_workspace_references(workspace_id, path_id, run_id)

@router.get("/{workspace_id}/regions")
def get_regions(workspace_id: str, path_id: str, run_id: str | None = None):
    return get_workspace_regions(workspace_id, path_id, run_id)

@router.get("/{workspace_id}/patches")
def get_patches(workspace_id: str, run_id: str | None = None):
    return get_persisted_patches(workspace_id, run_id)

@router.get("/{workspace_id}/replays")
def get_replays(workspace_id: str, run_id: str | None = None):
    return get_persisted_replays(workspace_id, run_id)

@router.get("/{workspace_id}/simulations")
def get_simulations(workspace_id: str, run_id: str | None = None):
    return get_persisted_simulations(workspace_id, run_id)

@router.get("/{workspace_id}/readiness")
def get_readiness(workspace_id: str, run_id: str | None = None):
    return get_execution_readiness(workspace_id, run_id)


@router.get("/{workspace_id}/project-state")
def get_project_state(workspace_id: str):
    try:
        ProjectMemory.initialize_project(workspace_id, "unknown")
        return ProjectMemory.get_project_state(workspace_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/{workspace_id}/project-summary")
def get_project_summary(workspace_id: str):
    try:
        return ProjectMemory.describe_project(workspace_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/{workspace_id}/workspace-awareness")
def get_workspace_awareness(workspace_id: str, run_id: str | None = None, prompt: str | None = None):
    try:
        return WorkspaceAwareness.scan(workspace_id, run_id=run_id, prompt=prompt)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/{workspace_id}/workspace-summary")
def get_workspace_summary(workspace_id: str):
    try:
        return WorkspaceAwareness.describe(workspace_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/{workspace_id}/change-scope")
def get_change_scope(workspace_id: str, prompt: str | None = None, run_id: str | None = None):
    try:
        if prompt:
            ProjectMemory.initialize_project(workspace_id, "unknown")
            state = ProjectMemory.get_project_state(workspace_id)
            action = ProjectMemory.classify_action(workspace_id, prompt)
            awareness = WorkspaceAwareness.scan(workspace_id, run_id=run_id, prompt=prompt)
            return ChangeScopeAnalyzer.analyze(
                workspace_id,
                prompt,
                project_state=state,
                project_action=action,
                workspace_awareness=awareness,
            )
        scope = ChangeScopeAnalyzer.load(workspace_id)
        if not scope:
            raise FileNotFoundError("Change scope analysis not found")
        return scope
    except Exception as exc:
        raise _http_error(exc)


@router.get("/{workspace_id}/reflection")
def get_reflection_engine(workspace_id: str):
    try:
        return ReflectionEngine.load(workspace_id)
    except Exception as exc:
        raise _http_error(exc)
