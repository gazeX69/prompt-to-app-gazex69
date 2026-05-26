import datetime
import json
import re
import time
from pathlib import Path
from typing import Any, Optional


WORKSPACES_ROOT = Path("workspaces")
MANIFEST_DIR_NAME = ".ai-agent"
PROJECT_STATUS_FILE = "generation_status.json"
RUNS_DIR_NAME = "runs"
ALLOWED_STATUSES = {"accepted", "running", "succeeded", "failed", "interrupted", "unknown"}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_project_root(project_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", project_id or ""):
        raise ValueError("Invalid project_id")
    root = WORKSPACES_ROOT.resolve()
    project_root = (WORKSPACES_ROOT / project_id).resolve()
    try:
        project_root.relative_to(root)
    except ValueError as exc:
        raise ValueError("Project path escapes workspace root") from exc
    return project_root


def _safe_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", run_id or ""):
        raise ValueError("Invalid run_id")
    return run_id


def _manifest_root(project_id: str, *, create: bool = False) -> Path:
    path = _safe_project_root(project_id) / MANIFEST_DIR_NAME
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _runs_root(project_id: str, *, create: bool = False) -> Path:
    path = _manifest_root(project_id, create=create) / RUNS_DIR_NAME
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _write_json(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)
    return data


def _project_status_path(project_id: str) -> Path:
    return _manifest_root(project_id) / PROJECT_STATUS_FILE


def _run_manifest_path(project_id: str, run_id: str) -> Path:
    return _runs_root(project_id) / f"{_safe_run_id(run_id)}.json"


def normalize_generation_status(status: str | None) -> str:
    if status == "generating":
        return "running"
    if status in {"completed", "runtime_ready"}:
        return "succeeded"
    if status in ALLOWED_STATUSES:
        return status or "unknown"
    return "unknown"


def read_project_generation_status(project_id: str) -> Optional[dict[str, Any]]:
    return _read_json(_project_status_path(project_id))


def read_run_manifest(project_id: str, run_id: str) -> Optional[dict[str, Any]]:
    return _read_json(_run_manifest_path(project_id, run_id))


def _default_project_status(project_id: str) -> dict[str, Any]:
    now = _now_iso()
    return {
        "project_id": project_id,
        "latest_run_id": None,
        "active_run_id": None,
        "current_run_id": None,
        "generation_id": None,
        "status": "unknown",
        "created_at": now,
        "updated_at": now,
        "runs": [],
    }


def _upsert_run_summary(project_status: dict[str, Any], run_manifest: dict[str, Any]) -> None:
    run_id = run_manifest.get("run_id")
    if not run_id:
        return

    summary = {
        "run_id": run_id,
        "status": run_manifest.get("status") or "unknown",
        "active": bool(run_manifest.get("active")),
        "created_at": run_manifest.get("created_at"),
        "updated_at": run_manifest.get("updated_at"),
        "completed_at": run_manifest.get("completed_at"),
        "prompt": run_manifest.get("prompt"),
    }

    existing_runs = project_status.get("runs")
    runs = existing_runs if isinstance(existing_runs, list) else []
    runs = [item for item in runs if not isinstance(item, dict) or item.get("run_id") != run_id]
    project_status["runs"] = [summary, *runs][:50]


def record_project_generation_status(
    project_id: str,
    *,
    status: str,
    generation_id: str | None = None,
    run_id: str | None = None,
    prompt: str | None = None,
    error: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = normalize_generation_status(status)
    now = _now_iso()
    project_status = read_project_generation_status(project_id) or _default_project_status(project_id)
    project_status.update(
        {
            "project_id": project_id,
            "generation_id": generation_id or project_status.get("generation_id"),
            "current_run_id": run_id or project_status.get("current_run_id"),
            "status": normalized_status,
            "updated_at": now,
            "updatedAt": _now_ms(),
            "error": error,
            "detail": detail or {},
        }
    )
    if prompt is not None:
        project_status["prompt"] = prompt

    return _write_json(_project_status_path(project_id), project_status)


def record_run_manifest(
    project_id: str,
    run_id: str,
    *,
    status: str,
    generation_id: str | None = None,
    prompt: str | None = None,
    error: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_status = normalize_generation_status(status)
    now = _now_iso()
    existing = read_run_manifest(project_id, run_id) or {}
    completed_at = existing.get("completed_at")
    if normalized_status in {"succeeded", "failed", "interrupted"}:
        completed_at = completed_at or now

    manifest = {
        "project_id": project_id,
        "run_id": _safe_run_id(run_id),
        "generation_id": generation_id or existing.get("generation_id"),
        "status": normalized_status,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "completed_at": completed_at,
        "active": normalized_status == "succeeded",
        "prompt": prompt if prompt is not None else existing.get("prompt"),
        "error": error,
        "detail": detail or existing.get("detail") or {},
    }
    _write_json(_run_manifest_path(project_id, run_id), manifest)

    project_status = read_project_generation_status(project_id) or _default_project_status(project_id)
    project_status.update(
        {
            "project_id": project_id,
            "generation_id": generation_id or project_status.get("generation_id"),
            "current_run_id": run_id,
            "status": normalized_status,
            "updated_at": now,
            "updatedAt": _now_ms(),
            "error": error,
            "detail": detail or {},
        }
    )
    if prompt is not None:
        project_status["prompt"] = prompt

    if normalized_status == "succeeded":
        project_status["active_run_id"] = run_id
        project_status["latest_run_id"] = run_id

    _upsert_run_summary(project_status, manifest)
    _write_json(_project_status_path(project_id), project_status)
    return manifest


def mark_current_run(
    project_id: str,
    *,
    status: str,
    generation_id: str | None = None,
    prompt: str | None = None,
    error: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_status = read_project_generation_status(project_id)
    run_id = (project_status or {}).get("current_run_id")
    if run_id:
        return record_run_manifest(
            project_id,
            run_id,
            status=status,
            generation_id=generation_id,
            prompt=prompt,
            error=error,
            detail=detail,
        )
    return record_project_generation_status(
        project_id,
        status=status,
        generation_id=generation_id,
        prompt=prompt,
        error=error,
        detail=detail,
    )

