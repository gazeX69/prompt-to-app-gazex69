from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
from pathlib import Path
from typing import Any

from backend.core.scanner.run_manifest import read_project_generation_status
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
from backend.core.dependency_resolution import resolve_dependency_health
from backend.sandbox.executor import get_runtime_status
from backend.memory.project_memory import ProjectMemory
from backend.memory.workspace_awareness import WorkspaceAwareness
from backend.brain.change_scope import ChangeScopeAnalyzer
from backend.reflection.reflection_engine import ReflectionEngine

router = APIRouter()

WORKSPACES_ROOT = Path("workspaces")


def _safe_workspace_root(workspace_id: str) -> Path:
    root = WORKSPACES_ROOT.resolve()
    workspace = (WORKSPACES_ROOT / workspace_id).resolve()
    workspace.relative_to(root)
    return workspace


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _file_state(workspace_root: Path, relative_path: str) -> dict[str, Any]:
    path = workspace_root / relative_path
    exists = path.exists()
    modified = None
    if exists:
        try:
            modified = path.stat().st_mtime
        except OSError:
            modified = None
    return {
        "path": relative_path,
        "exists": exists,
        "last_modified": modified,
    }


def _latest_discovery_session(workspace_root: Path) -> dict[str, Any] | None:
    sessions_dir = workspace_root / ".ai-agent" / "discovery_sessions"
    if not sessions_dir.exists():
        return None
    candidates = sorted(
        [path for path in sessions_dir.glob("*.json") if path.is_file()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        data = _read_json_file(path)
        if data:
            return data
    return None


def _stage_status(data: Any, *, failed: bool = False) -> str:
    if failed:
        return "failed"
    if data is None:
        return "missing"
    if isinstance(data, dict) and not data:
        return "unknown"
    return "loaded"


def _contract_for_project_type(project_type: str | None) -> dict[str, Any] | None:
    if not project_type:
        return None
    contract_key = "crud_app" if project_type == "crud" else project_type
    try:
        from backend.brain.domain_contract_registry import load_contract

        return load_contract(contract_key)
    except Exception:
        return None


def _collect_observatory_errors(
    generation_status: dict[str, Any] | None,
    runtime_status: dict[str, Any] | None,
    reflection_state: dict[str, Any] | None,
    dependency_health: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if generation_status and generation_status.get("error"):
        message = str(generation_status.get("error"))
        lower = message.lower()
        stage = "preview" if "preview" in lower else "runtime" if "runtime" in lower else "build" if "build" in lower else "generation"
        errors.append({"source": "generation", "stage": stage, "message": message})
    if runtime_status and runtime_status.get("error"):
        errors.append({"source": "runtime", "stage": "runtime", "message": str(runtime_status.get("error"))})
    for cycle in (reflection_state or {}).get("cycles") or []:
        for error in cycle.get("errors") or []:
            errors.append({
                "source": "reflection",
                "stage": cycle.get("stage") or "reflection",
                "message": error.get("message") or error.get("code") or "Reflection error",
                "code": error.get("code"),
            })
    for item in (dependency_health or {}).get("missing_dependencies") or []:
        errors.append({
            "source": "dependency",
            "stage": "dependency_resolution",
            "message": f"{item.get('package')} missing from package.json ({item.get('classification')})",
            "code": "E_DEPENDENCY_MISSING",
        })
    for item in (dependency_health or {}).get("invalid_dependencies") or []:
        errors.append({
            "source": "dependency",
            "stage": "dependency_resolution",
            "message": f"{item.get('package')} is not a valid dependency for this layer",
            "code": "E_DEPENDENCY_INVALID",
        })
    return errors[:30]

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


def _runtime_state(status: str | None) -> str:
    return str(status or "").lower()


def _with_runtime_status(workspace: dict) -> dict:
    runtime_status = get_runtime_status(workspace["id"])
    status = _runtime_state(runtime_status.get("status") or workspace.get("status") or "unknown")
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
    if _runtime_state(runtime_status.get("status")) not in {"", "unknown", "stopped", "failed", "crashed"}:
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


@router.get("/{workspace_id}/debug-observatory")
def get_debug_observatory(workspace_id: str):
    try:
        workspace_root = _safe_workspace_root(workspace_id)
        ai_root = workspace_root / ".ai-agent"
        discovery_state = _latest_discovery_session(workspace_root)
        project_state = ProjectMemory.get_project_state(workspace_id)
        change_scope = ChangeScopeAnalyzer.load(workspace_id)
        workspace_awareness = WorkspaceAwareness.load(workspace_id)
        reflection_state = ReflectionEngine.load(workspace_id)
        generation_status = read_project_generation_status(workspace_id)
        runtime_status = get_runtime_status(workspace_id)
        loaded_contract = _contract_for_project_type((project_state or {}).get("project_type"))
        try:
            dependency_health = resolve_dependency_health(workspace_id)
        except Exception:
            dependency_health = _read_json_file(workspace_root / ".ai-agent" / "dependency_resolution.json") or {
                "status": "missing",
                "detected_imports": [],
                "declared_dependencies": [],
                "missing_dependencies": [],
                "framework_dependencies": [],
                "feature_dependencies": [],
                "invalid_dependencies": [],
                "repair_strategy": [],
                "repair_result": "unknown",
            }

        file_paths = {
            "project_state": ".ai-agent/project_state.json",
            "change_scope": ".ai-agent/change_scope_analysis.json",
            "workspace_awareness": ".ai-agent/workspace_awareness.json",
            "reflection": ".ai-agent/reflection_engine.json",
            "generation_status": ".ai-agent/generation_status.json",
        }
        files = {key: _file_state(workspace_root, rel_path) for key, rel_path in file_paths.items()}

        state_flow = [
            {
                "stage": "Discovery",
                "status": _stage_status(discovery_state),
                "detail": (discovery_state or {}).get("current_node") or ("complete" if (discovery_state or {}).get("complete") else None),
            },
            {
                "stage": "Project State",
                "status": _stage_status(project_state, failed=False if project_state is not None else False),
                "detail": (project_state or {}).get("project_type"),
            },
            {
                "stage": "Change Scope",
                "status": _stage_status(change_scope),
                "detail": (change_scope or {}).get("scope_size"),
            },
            {
                "stage": "Generator",
                "status": _stage_status(generation_status, failed=(generation_status or {}).get("status") == "failed"),
                "detail": (generation_status or {}).get("status"),
            },
            {
                "stage": "Reflection",
                "status": _stage_status(reflection_state),
                "detail": ((reflection_state or {}).get("reflection_score") or {}).get("grade"),
            },
            {
                "stage": "Runtime",
                "status": _stage_status(runtime_status, failed=str((runtime_status or {}).get("status") or "").lower() in {"failed", "crashed"}),
                "detail": (runtime_status or {}).get("status"),
            },
        ]

        return {
            "workspace_id": workspace_id,
            "observatory_enabled": False,
            "discovery_state": {
                "session_id": (discovery_state or {}).get("session_id"),
                "current_node": (discovery_state or {}).get("current_node"),
                "completed": bool((discovery_state or {}).get("complete")),
                "answers": (discovery_state or {}).get("answers") or {},
                "draft_state": (discovery_state or {}).get("draft_state") or {},
            },
            "project_state": {
                "project_type": (project_state or {}).get("project_type"),
                "domain": (project_state or {}).get("domain"),
                "database": (project_state or {}).get("database"),
                "supplier": (project_state or {}).get("supplier"),
                "source": ".ai-agent/project_state.json" if files["project_state"]["exists"] else None,
                "last_updated": (project_state or {}).get("updated_at"),
            },
            "state_flow": state_flow,
            "generator_context": {
                "final_prompt": (generation_status or {}).get("prompt"),
                "loaded_contract": {
                    "app_type": (loaded_contract or {}).get("app_type"),
                    "contract_version": (loaded_contract or {}).get("contract_version") or (loaded_contract or {}).get("version"),
                    "features": (loaded_contract or {}).get("features") or (loaded_contract or {}).get("feature_keywords") or [],
                } if loaded_contract else None,
                "project_state_used": {
                    "project_type": (project_state or {}).get("project_type"),
                    "domain": (project_state or {}).get("domain"),
                    "database": (project_state or {}).get("database"),
                    "supplier": (project_state or {}).get("supplier"),
                },
                "generation_mode": (generation_status or {}).get("phase") or (generation_status or {}).get("status"),
            },
            "dependency_health": dependency_health,
            "error_center": _collect_observatory_errors(generation_status, runtime_status, reflection_state, dependency_health),
            "state_files": files,
            "workspace_awareness": workspace_awareness,
            "change_scope": change_scope,
            "reflection_state": reflection_state,
            "runtime_state": runtime_status,
            "ai_root": str(ai_root),
        }
    except Exception as exc:
        raise _http_error(exc)
