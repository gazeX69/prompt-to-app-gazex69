from datetime import datetime, timezone
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from backend.brain.plan_signature import build_plan_signature
from backend.brain.prompt_cleaning import clean_user_intent_prompt
from backend.memory.db import get_connection

logger = logging.getLogger(__name__)

PROJECT_STATE_SCHEMA_VERSION = "p9.project_state.v1"
PROJECT_STATE_RELATIVE_PATH = ".ai-agent/project_state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "workspaces"


def _validate_project_id(project_id: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", project_id or ""):
        raise ValueError(f"Invalid project_id: {project_id!r}")
    return project_id


def _state_path(project_id: str) -> Path:
    safe_id = _validate_project_id(project_id)
    root = _workspace_root().resolve()
    project_path = (root / safe_id).resolve()
    project_path.relative_to(root)
    return project_path / PROJECT_STATE_RELATIVE_PATH


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = (item or "").strip().lower().replace(" ", "_")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _default_state(project_id: str, ecosystem: str = "unknown") -> dict[str, Any]:
    now = _utc_now()
    return {
        "schema_version": PROJECT_STATE_SCHEMA_VERSION,
        "project_id": project_id,
        "project_name": project_id,
        "ecosystem": ecosystem or "unknown",
        "project_type": "unknown",
        "features": [],
        "decisions": {},
        "active_context": {
            "current_goal": None,
            "last_prompt": None,
            "last_action": "create",
            "confidence": 0.0,
        },
        "known_missing": [],
        "status": "active",
        "maturity": {
            "level_1_state_file": True,
            "level_2_persistent": True,
            "level_3_updates_after_generate": False,
            "level_4_create_modify_detection": False,
            "level_5_preserve_existing_features": False,
            "level_6_duplicate_feature_awareness": False,
            "level_7_explainable_project": False,
        },
        "created_at": now,
        "updated_at": now,
    }


def _feature_hints(prompt: str) -> list[str]:
    text = (prompt or "").lower()
    hints = {
        "products": ["product", "produk", "barang", "catalog", "katalog"],
        "cart": ["cart", "keranjang"],
        "checkout": ["checkout", "order", "pesanan"],
        "payment": ["payment", "pembayaran", "midtrans", "stripe"],
        "admin": ["admin", "dashboard admin", "seller"],
        "wishlist": ["wishlist", "favorit", "favorite", "simpan produk"],
        "auth": ["login", "auth", "register", "authentication"],
        "roles": ["role", "permission", "admin/user"],
        "reports": ["report", "laporan", "analytics", "metric"],
        "inventory": ["inventory", "inventori", "stok", "stock"],
        "search": ["search", "cari", "filter"],
        "crud": ["crud", "create", "edit", "update", "delete", "hapus", "tambah"],
    }
    return [feature for feature, terms in hints.items() if any(term in text for term in terms)]


def _project_type_defaults(app_type: str) -> list[str]:
    defaults = {
        "marketplace": ["products", "cart", "checkout", "admin"],
        "inventory": ["inventory", "crud", "reports"],
        "todo": ["tasks", "crud"],
        "crud": ["crud"],
        "crud_app": ["crud"],
        "dashboard": ["dashboard", "reports"],
        "pos": ["products", "cart", "payment", "reports"],
    }
    return defaults.get(app_type, [])


def _is_new_app_request_against_existing_state(state: dict | None, prompt: str) -> bool:
    if not state:
        return False
    existing_type = (state.get("project_type") or "unknown").strip().lower()
    if existing_type == "unknown":
        return False
    try:
        signature = build_plan_signature(clean_user_intent_prompt(prompt))
    except Exception:
        return False
    requested_type = (getattr(signature, "app_type", "") or "").strip().lower()
    explicit_new_app_types = {
        "marketplace",
        "inventory",
        "dashboard",
        "recruitment",
        "finance",
        "booking",
        "pos",
        "cms",
        "lms",
        "saas",
        "social media",
    }
    if not requested_type or requested_type == "app" or requested_type == existing_type:
        return False
    if requested_type not in explicit_new_app_types:
        return False
    if getattr(signature, "intent", "") != "build_app":
        return False
    return True


def _decision_hints(prompt: str) -> dict[str, str]:
    text = (prompt or "").lower()
    decisions: dict[str, str] = {}
    if "localstorage" in text or "local storage" in text:
        decisions["persistence"] = "localStorage"
    if "supabase" in text:
        decisions["database"] = "supabase"
    elif "sqlite" in text:
        decisions["database"] = "sqlite"
    elif "postgres" in text:
        decisions["database"] = "postgres"
    elif "database" in text or "db" in text:
        decisions.setdefault("database", "unspecified_database")
    if "midtrans" in text:
        decisions["payment"] = "midtrans"
    elif "stripe" in text:
        decisions["payment"] = "stripe"
    elif "simulated checkout" in text or "checkout simulation" in text or "simulasi" in text:
        decisions["payment"] = "simulated"
    return decisions


class ProjectMemory:
    @staticmethod
    def initialize_project(project_id: str, ecosystem: str):
        with get_connection() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO project_memory (id, ecosystem)
                VALUES (?, ?)
            ''', (project_id, ecosystem))
            conn.commit()
        state = ProjectMemory.load_project_state(project_id)
        if state is None:
            state = _default_state(project_id, ecosystem)
        elif ecosystem and state.get("ecosystem") in {None, "", "unknown", "blank"}:
            state["ecosystem"] = ecosystem
            state["updated_at"] = _utc_now()
        ProjectMemory.save_project_state(project_id, state)

    @staticmethod
    def update_architecture_notes(project_id: str, notes: str):
        with get_connection() as conn:
            conn.execute('''
                UPDATE project_memory 
                SET architecture_notes = ? 
                WHERE id = ?
            ''', (notes, project_id))
            conn.commit()

    @staticmethod
    def get_project_state(project_id: str) -> Optional[dict]:
        file_state = ProjectMemory.load_project_state(project_id)
        if file_state:
            return file_state
        with get_connection() as conn:
            cur = conn.execute('SELECT * FROM project_memory WHERE id = ?', (project_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def load_project_state(project_id: str) -> Optional[dict]:
        path = _state_path(project_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def save_project_state(project_id: str, state: dict) -> dict:
        path = _state_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {**_default_state(project_id, state.get("ecosystem") or "unknown"), **state}
        state["schema_version"] = PROJECT_STATE_SCHEMA_VERSION
        state["project_id"] = project_id
        state["features"] = _unique(list(state.get("features") or []))
        state["known_missing"] = _unique(list(state.get("known_missing") or []))
        state["updated_at"] = _utc_now()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return state

    @staticmethod
    def load_for(project_id: str, consumer: str, ecosystem: str | None = None) -> dict:
        state = ProjectMemory.load_project_state(project_id)
        if state is None:
            state = _default_state(project_id, ecosystem or "unknown")
            state = ProjectMemory.save_project_state(project_id, state)
        logger.info("[ProjectState] Loaded for %s", consumer)
        for key in ["project_type", "domain", "database", "supplier"]:
            if key in state:
                logger.info("[ProjectState] %s=%s", key, str(state.get(key)).lower() if isinstance(state.get(key), bool) else state.get(key))
        return state

    @staticmethod
    def update_from_discovery_draft(
        project_id: str,
        draft_state: dict[str, Any],
        *,
        session_id: str | None = None,
        ecosystem: str | None = None,
    ) -> dict:
        state = ProjectMemory.load_project_state(project_id) or _default_state(project_id, ecosystem or "unknown")
        if ecosystem and state.get("ecosystem") in {None, "", "unknown", "blank"}:
            state["ecosystem"] = ecosystem
        allowed_top_level = {"project_type", "domain", "database", "supplier"}
        for key in allowed_top_level:
            if key in draft_state:
                state[key] = draft_state[key]
        if state.get("project_type") and state.get("project_type") != "unknown" and state.get("project_name") == project_id:
            label = str(state["project_type"])
            if state.get("domain"):
                label = f"{state['domain']} {label}"
            state["project_name"] = label.replace("_", " ").title()
        decisions = dict(state.get("decisions") or {})
        for key, value in draft_state.items():
            if key != "project_type":
                decisions[key] = value
        state["decisions"] = decisions
        features = list(state.get("features") or [])
        if draft_state.get("domain"):
            features.append(str(draft_state["domain"]))
        if draft_state.get("project_type"):
            features.extend(_project_type_defaults(str(draft_state["project_type"])))
        state["features"] = _unique(features)
        active_context = dict(state.get("active_context") or {})
        active_context.update({
            "last_action": "discovery",
            "discovery_session_id": session_id,
            "current_goal": "Discovery completed",
            "confidence": max(float(active_context.get("confidence") or 0.0), 0.82),
        })
        state["active_context"] = active_context
        maturity = dict(state.get("maturity") or {})
        maturity["level_8_discovery_state_sync"] = True
        state["maturity"] = maturity
        logger.info("[ProjectState] Updated from discovery session")
        return ProjectMemory.save_project_state(project_id, state)

    @staticmethod
    def classify_action(project_id: str, prompt: str) -> dict:
        state = ProjectMemory.load_project_state(project_id)
        clean_prompt = clean_user_intent_prompt(prompt)
        text = clean_prompt.lower()
        features = set((state or {}).get("features") or [])
        has_existing_project = bool(state and ((state.get("project_type") or "unknown") != "unknown" or features))
        modify_terms = ["tambah", "tambahkan", "ubah", "update", "edit", "hapus", "perbaiki", "fix", "add", "modify"]
        create_terms = ["buat", "build", "create", "make", "generate"]
        resets_existing_state = _is_new_app_request_against_existing_state(state, clean_prompt)

        if resets_existing_state:
            action = "create"
            confidence = 0.91
        elif has_existing_project and any(term in text for term in modify_terms):
            action = "modify"
            confidence = 0.86
        elif not has_existing_project and any(term in text for term in create_terms):
            action = "create"
            confidence = 0.84
        elif has_existing_project:
            action = "modify"
            confidence = 0.64
        else:
            action = "create"
            confidence = 0.58

        requested_features = _feature_hints(clean_prompt)
        duplicate_features = sorted(set(requested_features) & features)
        missing_features = sorted(set(requested_features) - features)
        return {
            "action": action,
            "confidence": confidence,
            "requested_features": requested_features,
            "duplicate_features": duplicate_features,
            "missing_features": missing_features,
            "has_existing_project": has_existing_project,
            "state_inheritance": "reset" if resets_existing_state else ("inherit" if has_existing_project else "none"),
            "clean_prompt": clean_prompt,
        }

    @staticmethod
    def update_after_generation(
        project_id: str,
        prompt: str,
        signature=None,
        ecosystem: str | None = None,
        success: bool = True,
    ) -> dict:
        state = ProjectMemory.load_project_state(project_id) or _default_state(project_id, ecosystem or "unknown")
        clean_prompt = clean_user_intent_prompt(prompt)
        action = ProjectMemory.classify_action(project_id, clean_prompt)
        if ecosystem:
            state["ecosystem"] = ecosystem
        if signature is not None:
            app_type = getattr(signature, "app_type", None)
            if app_type and app_type != "app":
                state["project_type"] = app_type
                if state.get("project_name") == project_id:
                    state["project_name"] = app_type.replace("_", " ").title()
            features = list(getattr(signature, "feature_keywords", []) or [])
            features.extend(_project_type_defaults(app_type or ""))
        else:
            features = []
        features.extend(_feature_hints(clean_prompt))

        state["features"] = _unique(list(state.get("features") or []) + features)
        state["decisions"] = {**(state.get("decisions") or {}), **_decision_hints(prompt)}
        state["active_context"] = {
            "current_goal": clean_prompt.strip()[:160] if clean_prompt else None,
            "last_prompt": clean_prompt,
            "last_action": action["action"],
            "confidence": action["confidence"],
            "duplicate_features": action["duplicate_features"],
            "missing_features": action["missing_features"],
            "state_inheritance": action.get("state_inheritance"),
        }
        state["status"] = "active" if success else "needs_attention"
        maturity = dict(state.get("maturity") or {})
        maturity.update({
            "level_1_state_file": True,
            "level_2_persistent": True,
            "level_3_updates_after_generate": success,
            "level_4_create_modify_detection": True,
            "level_5_preserve_existing_features": True,
            "level_6_duplicate_feature_awareness": True,
            "level_7_explainable_project": True,
        })
        state["maturity"] = maturity
        return ProjectMemory.save_project_state(project_id, state)

    @staticmethod
    def build_state_context(project_id: str, prompt: str | None = None) -> str:
        state = ProjectMemory.get_project_state(project_id)
        if not state:
            return "=== PROJECT STATE ===\nNo project state exists yet. Treat this as a create request with low confidence.\n=== END PROJECT STATE ==="
        action = ProjectMemory.classify_action(project_id, prompt or "")
        features = ", ".join(state.get("features") or []) or "none recorded"
        decisions = state.get("decisions") or {}
        discovered = {
            key: state.get(key)
            for key in ["domain", "database", "supplier"]
            if key in state
        }
        duplicate = ", ".join(action["duplicate_features"]) or "none"
        missing = ", ".join(action["missing_features"]) or "none"
        return (
            "=== PROJECT STATE ===\n"
            "Epistemic rule: Project State is the current best known state, not absolute truth.\n"
            f"Project: {state.get('project_name')} ({state.get('project_type')})\n"
            f"Ecosystem: {state.get('ecosystem')}\n"
            f"Discovered state: {json.dumps(discovered, ensure_ascii=False)}\n"
            f"Existing features: {features}\n"
            f"Decisions: {json.dumps(decisions, ensure_ascii=False)}\n"
            f"Predicted action: {action['action']} (confidence={action['confidence']:.2f})\n"
            f"Already existing requested features: {duplicate}\n"
            f"New requested features: {missing}\n"
            "Rules:\n"
            "- For modify requests, preserve existing features and add only the requested capability.\n"
            "- Do not recreate or duplicate features already listed in Project State.\n"
            "- If Project State conflicts with source code, prefer a cautious patch and update state after validation.\n"
            "=== END PROJECT STATE ==="
        )

    @staticmethod
    def describe_project(project_id: str) -> dict:
        state = ProjectMemory.get_project_state(project_id)
        if not state:
            raise FileNotFoundError("Project state not found")
        features = state.get("features") or []
        decisions = state.get("decisions") or {}
        known_missing = state.get("known_missing") or []
        summary_lines = [
            f"{state.get('project_name') or project_id} adalah project {state.get('project_type')} berbasis {state.get('ecosystem')}.",
            "Fitur yang tercatat: " + (", ".join(features) if features else "belum ada fitur tercatat") + ".",
            "Keputusan teknis: " + (", ".join(f"{k}={v}" for k, v in decisions.items()) if decisions else "belum ada keputusan tercatat") + ".",
            "Belum ada: " + (", ".join(known_missing) if known_missing else "belum tercatat") + ".",
        ]
        return {
            "project_state": state,
            "summary": "\n".join(summary_lines),
            "confidence": 0.78 if features else 0.52,
            "source": PROJECT_STATE_RELATIVE_PATH,
        }
