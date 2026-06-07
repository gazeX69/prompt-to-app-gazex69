import json
import re
import uuid
from pathlib import Path

from backend.brain.discovery_tree.node_schema import DiscoverySessionState

DISCOVERY_SESSION_RELATIVE_DIR = ".ai-agent/discovery_sessions"


class DiscoverySessionError(RuntimeError):
    pass


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "workspaces"


def _validate_id(value: str, label: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", value or ""):
        raise DiscoverySessionError(f"Invalid {label}: {value!r}")
    return value


def _session_base_dir(project_id: str | None = None) -> Path:
    if project_id:
        safe_project = _validate_id(project_id, "project_id")
        root = _workspace_root().resolve()
        project_path = (root / safe_project).resolve()
        project_path.relative_to(root)
        return project_path / DISCOVERY_SESSION_RELATIVE_DIR
    return Path(__file__).resolve().parent.parent / "memory" / "discovery_sessions"


def _session_path(session_id: str, project_id: str | None = None) -> Path:
    safe_session = _validate_id(session_id, "session_id")
    return _session_base_dir(project_id) / f"{safe_session}.json"


def create_session(root_node: str, project_id: str | None = None) -> DiscoverySessionState:
    session = DiscoverySessionState(
        session_id=f"disc_{uuid.uuid4().hex[:10]}",
        root_node=root_node,
        current_node=root_node,
    )
    save_session(session, project_id)
    return session


def save_session(session: DiscoverySessionState, project_id: str | None = None) -> DiscoverySessionState:
    path = _session_path(session.session_id, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    payload = session.model_dump() if hasattr(session, "model_dump") else session.dict()
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return session


def load_session(session_id: str, project_id: str | None = None) -> DiscoverySessionState:
    path = _session_path(session_id, project_id)
    if not path.exists():
        raise DiscoverySessionError(f"Discovery session not found: {session_id}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiscoverySessionError(f"Invalid discovery session JSON: {session_id}") from exc
    return DiscoverySessionState(**data)
