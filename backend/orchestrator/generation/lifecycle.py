import asyncio
import datetime
import json
import shutil
from pathlib import Path

from backend.agent.tools import append_file
from backend.sandbox.executor import _safe_project_path
from backend.sockets.manager import emit_agent_activity

_ECOSYSTEM_LABELS = {
    "react-vite": "React + Vite + TypeScript",
    "node-backend": "Node.js",
    "php-basic": "PHP",
    "laravel": "Laravel PHP",
}


def _ecosystem_label(name: str) -> str:
    return _ECOSYSTEM_LABELS.get(name, name)


def _copy_project_tree(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    workspace_root = Path("workspaces").resolve()
    source.relative_to(workspace_root)
    destination.relative_to(workspace_root)
    if source == destination:
        return

    def ignore_transient(_dir: str, names: list[str]) -> set[str]:
        ignored = {".orchestration", "node_modules", "dist", "build", ".vite", "__pycache__"}
        return {name for name in names if name in ignored}

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=ignore_transient)


def _active_source_dir(project_id: str) -> Path | None:
    project_root = _safe_project_path(project_id)
    try:
        from backend.core.scanner.run_manifest import get_active_successful_run_id

        active_run_id = get_active_successful_run_id(project_id)
    except Exception:
        active_run_id = None
    candidates: list[Path] = []
    if active_run_id:
        candidates.append(_safe_project_path(project_id, active_run_id))
    candidates.append(_safe_project_path(project_id, "latest"))
    candidates.extend(
        sorted(
            [path for path in project_root.glob("run_*") if path.is_dir()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    )
    for candidate in candidates:
        if candidate.exists() and (
            (candidate / "package.json").exists()
            or (candidate / "src").exists()
            or (candidate / "index.html").exists()
        ):
            return candidate
    return None


def _initialize_modify_run_from_current_state(project_id: str, run_id: str, project_action: dict | None) -> bool:
    if not project_action or project_action.get("action") != "modify" or not project_action.get("has_existing_project"):
        return False
    source = _active_source_dir(project_id)
    if not source:
        return False
    destination = _safe_project_path(project_id, run_id)
    _copy_project_tree(source, destination)
    return True


def _sync_run_to_latest(project_id: str, run_id: str) -> bool:
    source = _safe_project_path(project_id, run_id)
    if not source.exists():
        return False
    destination = _safe_project_path(project_id, "latest")
    _copy_project_tree(source, destination)
    return True

def _get_allowed_dependencies(project_path) -> list[str]:
    import json
    from pathlib import Path
    try:
        pkg_path = Path(project_path) / "package.json"
        if pkg_path.exists():
            pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
            deps = pkg_data.get("dependencies", {})
            return list(deps.keys())
    except Exception:
        pass
    return []


async def _log_work_async(project_id: str, run_id: str, message: str):
    await asyncio.to_thread(append_file, project_id, "WORKLOG.md", f"- {message}", run_id)
    try:
        await emit_agent_activity(message, project_id)
    except Exception:
        pass


async def _log_error_async(project_id: str, run_id: str, error: str):
    ts = datetime.datetime.now().isoformat()
    await asyncio.to_thread(append_file, project_id, "ERROR_LOG.md", f"## Error at {ts}\n\n```\n{error}\n```\n", run_id)

