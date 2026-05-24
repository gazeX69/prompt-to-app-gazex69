from fastapi import APIRouter, HTTPException

from backend.core.scanner.workspace_scanner import (
    scan_workspaces,
    get_workspace_runs,
    get_workspace_tree,
    get_workspace_artifacts,
    get_workspace_artifact_content,
    get_workspace_file_content,
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

router = APIRouter()

@router.get("")
def list_workspaces():
    return scan_workspaces()

@router.get("/{workspace_id}")
def get_workspace(workspace_id: str):
    wses = scan_workspaces()
    for w in wses:
        if w["id"] == workspace_id:
            return w
    raise HTTPException(status_code=404, detail="Workspace not found")

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
