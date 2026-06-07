import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_STATE_SCHEMA_VERSION = "p9.project_state.v1"
PROJECT_STATE_RELATIVE_PATH = ".ai-agent/project_state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent / "workspaces"


def get_state_path(project_id: str) -> Path:
    root = _get_workspace_root().resolve()
    project_path = (root / project_id).resolve()
    # Security/bounds check
    project_path.relative_to(root)
    return project_path / PROJECT_STATE_RELATIVE_PATH


class ProjectStateManager:
    @staticmethod
    def default_state(project_id: str, app_type: str = "unknown", domain: str = "unknown") -> Dict[str, Any]:
        now = _utc_now()
        return {
            "schema_version": PROJECT_STATE_SCHEMA_VERSION,
            "project_id": project_id,
            "project_type": app_type,
            "domain": domain,
            "goal": "",
            "current_phase": "planning",
            "completed_features": [],
            "pending_features": [],
            "implementation_plan": [],
            "decisions": {},
            "constraints": {
                "allowed_paths": [],
                "forbidden_paths": ["package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "index.html", "src/main.tsx"]
            },
            "validation_contract": {
                "expected_terms": [],
                "required_terms": [],
                "min_interactive": 0
            },
            "confidence": 0.0,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def load(project_id: str) -> Optional[Dict[str, Any]]:
        path = get_state_path(project_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.error("Failed to load project state for %s: %s", project_id, e)
        return None

    @staticmethod
    def save(project_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        path = get_state_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure default fields are present
        defaults = ProjectStateManager.default_state(project_id)
        merged = {**defaults, **state}
        merged["schema_version"] = PROJECT_STATE_SCHEMA_VERSION
        merged["project_id"] = project_id
        merged["updated_at"] = _utc_now()
        
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(path)
        except Exception as e:
            logger.error("Failed to write project state for %s: %s", project_id, e)
            raise e
        return merged

    @staticmethod
    def update_phase(project_id: str, phase: str):
        state = ProjectStateManager.load(project_id)
        if not state:
            state = ProjectStateManager.default_state(project_id)
        state["current_phase"] = phase
        ProjectStateManager.save(project_id, state)
