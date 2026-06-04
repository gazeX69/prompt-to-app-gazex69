from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any

from backend.memory.project_memory import ProjectMemory


CHANGE_SCOPE_SCHEMA_VERSION = "p11.change_scope.v1"
CHANGE_SCOPE_RELATIVE_PATH = ".ai-agent/change_scope_analysis.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "workspaces"


def _scope_path(project_id: str) -> Path:
    root = _workspace_root().resolve()
    project_path = (root / project_id).resolve()
    project_path.relative_to(root)
    return project_path / CHANGE_SCOPE_RELATIVE_PATH


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = (item or "").strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _classify_change_type(prompt: str) -> tuple[str, list[str]]:
    text = (prompt or "").lower()
    style_terms = ["background", "warna", "biru", "merah", "hijau", "css", "style", "tema", "theme", "font"]
    content_terms = ["tulisan", "teks", "text", "label", "judul", "subtitle", "di bawah", "dibawah", "bawah"]
    crud_terms = ["crud", "create", "read", "update", "delete", "tambah data", "edit data", "hapus data"]
    auth_terms = ["login", "register", "auth", "role", "permission", "token"]
    data_terms = ["database", "schema", "table", "model", "api", "backend", "server", "endpoint"]
    architecture_terms = ["refactor", "arsitektur", "architecture", "microservice", "state management", "routing", "rombak"]

    if _contains_any(text, architecture_terms):
        return "architecture_change", ["architecture", "routing", "state"]
    if _contains_any(text, auth_terms):
        return "auth_or_permission_change", ["auth", "routing", "api", "state"]
    if _contains_any(text, data_terms):
        return "data_or_api_change", ["data", "api", "state"]
    if _contains_any(text, crud_terms):
        return "feature_crud_change", ["ui", "state", "data"]
    if _contains_any(text, style_terms):
        return "style_update", ["ui", "style"]
    if _contains_any(text, content_terms):
        return "content_addition", ["ui", "content"]
    return "targeted_project_modification", ["ui"]


def _select_target_files(change_type: str, awareness: dict[str, Any] | None) -> list[str]:
    awareness = awareness or {}
    files = list((awareness.get("files") or {}).get("all") or [])
    impact = awareness.get("impact_analysis") or {}
    candidates = list(impact.get("candidate_files") or [])
    important = list((awareness.get("files") or {}).get("important") or [])

    def existing(preferred: list[str]) -> list[str]:
        known = set(files)
        return [item for item in preferred if item in known]

    if change_type == "style_update":
        preferred = existing(["src/App.css", "src/index.css", "src/App.tsx", "src/App.jsx", "index.html"])
        css_files = [path for path in files if path.endswith(".css")]
        app_files = existing(["src/App.tsx", "src/App.jsx"])
        return _unique(preferred + css_files[:3] + app_files)[:5]

    if change_type == "content_addition":
        return _unique(existing(["src/App.tsx", "src/App.jsx", "src/components/App.tsx"]) + candidates + important)[:5]

    if candidates:
        return _unique(candidates + important)[:8]

    return _unique(existing(["src/App.tsx", "src/App.jsx", "src/main.tsx", "index.html"]) + important)[:8]


def _scope_size(change_type: str, prompt: str, target_files: list[str], has_existing_project: bool) -> tuple[str, str, float]:
    text = (prompt or "").lower()
    broad_terms = ["lengkap", "kompleks", "full", "enterprise", "besar", "rombak", "semua", "multi role", "payment"]
    unclear_terms = ["bagus", "modern", "keren", "profesional", "rapikan"]

    if not has_existing_project:
        return "large", "create_without_existing_project_state", 0.58
    if change_type in {"style_update", "content_addition"} and len(target_files) <= 3:
        return "small", "single_ui_surface_change", 0.88
    if _contains_any(text, broad_terms) or change_type in {"architecture_change", "auth_or_permission_change"}:
        return "large", "broad_or_cross_cutting_change", 0.74
    if change_type in {"data_or_api_change", "feature_crud_change"}:
        return "medium", "feature_or_data_flow_change", 0.76
    if _contains_any(text, unclear_terms):
        return "unclear", "subjective_request_needs_narrowing", 0.62
    return "small", "localized_project_change", 0.78


def _required_validation(change_type: str, scope_size: str, awareness: dict[str, Any] | None) -> list[str]:
    stack = set(((awareness or {}).get("stack") or {}).get("stack") or [])
    checks = ["source_check"]
    if "react" in stack or "vite" in stack or change_type in {"style_update", "content_addition"}:
        checks.extend(["frontend_build", "preview_visual_check"])
    if change_type in {"data_or_api_change", "auth_or_permission_change"}:
        checks.extend(["unit_or_integration_tests", "runtime_smoke_test"])
    if scope_size in {"medium", "large"}:
        checks.append("regression_check")
    return _unique(checks)


def _safe_read(path: Path, limit: int = 200_000) -> str:
    try:
        if not path.exists() or not path.is_file() or path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _source_root(awareness: dict[str, Any] | None) -> Path | None:
    raw_root = (awareness or {}).get("source_root")
    if not raw_root:
        return None
    try:
        root = Path(str(raw_root)).resolve()
        workspace = _workspace_root().resolve()
        root.relative_to(workspace)
        return root
    except Exception:
        return None


def _extract_preserved_source_facts(
    prompt: str,
    change_type: str,
    target_files: list[str],
    awareness: dict[str, Any] | None,
) -> dict[str, Any]:
    root = _source_root(awareness)
    if root is None:
        return {
            "style_facts": [],
            "content_facts": [],
            "files_sampled": [],
            "confidence": 0.35,
        }

    sampled_files: list[str] = []
    style_facts: list[str] = []
    content_facts: list[str] = []
    files = list((awareness or {}).get("files", {}).get("all") or [])
    source_files = _unique(target_files + [path for path in files if path.endswith((".css", ".tsx", ".jsx", ".html"))])

    for rel_path in source_files[:12]:
        content = _safe_read(root / rel_path)
        if not content:
            continue
        sampled_files.append(rel_path)
        for match in re.finditer(r"(?i)\b(background(?:-color)?|color)\s*:\s*([^;}{]+)", content):
            style_facts.append(f"{rel_path}: preserve {match.group(1).lower()} = {match.group(2).strip()}")
        for match in re.finditer(r"(?i)(?:className|class)\s*=\s*['\"]([^'\"]+)['\"]", content):
            content_facts.append(f"{rel_path}: preserve class usage '{match.group(1).strip()}'")
        for match in re.finditer(r">\s*([^<>{}\n]{3,80})\s*<", content):
            text_value = re.sub(r"\s+", " ", match.group(1)).strip()
            if text_value and not text_value.startswith((".", "#")):
                content_facts.append(f"{rel_path}: preserve visible text '{text_value}'")

    text = (prompt or "").lower()
    relevant_facts = style_facts
    if change_type == "style_update":
        relevant_facts = content_facts + style_facts
    elif change_type == "content_addition":
        relevant_facts = style_facts + content_facts
    if any(term in text for term in ["background", "warna", "hijau", "biru", "merah"]):
        relevant_facts = style_facts + content_facts

    return {
        "style_facts": _unique(style_facts)[:20],
        "content_facts": _unique(content_facts)[:20],
        "relevant_preservation_facts": _unique(relevant_facts)[:24],
        "files_sampled": sampled_files[:12],
        "confidence": 0.82 if sampled_files else 0.42,
    }


def _clarifying_questions(change_type: str, scope_size: str, prompt: str, project_type: str) -> list[str]:
    if scope_size == "small":
        return []
    if scope_size == "unclear":
        return [
            f"Bagian mana dari project {project_type} yang ingin diubah terlebih dahulu?",
            "Perubahan ini harus hanya visual, atau boleh mengubah struktur komponen dan data?",
        ]
    if scope_size == "large":
        if change_type == "auth_or_permission_change":
            return [
                "Role apa saja yang wajib ada untuk perubahan ini?",
                "Auth cukup mock/local dulu atau harus terhubung ke backend/database?",
            ]
        if change_type == "architecture_change":
            return [
                "Area mana yang ingin dirombak terlebih dahulu agar perubahan tidak terlalu besar sekaligus?",
                "Bagian lama mana yang wajib dipertahankan?",
            ]
        return [
            "Fitur inti mana yang harus menjadi prioritas pertama?",
            "Apakah perubahan ini boleh menambah data model/API, atau hanya UI lokal dulu?",
        ]
    if scope_size == "medium" and change_type in {"data_or_api_change", "feature_crud_change"}:
        return [
            "Data apa saja yang wajib disimpan atau ditampilkan?",
            "Perubahan ini cukup localStorage/mock data dulu atau perlu backend?",
        ]
    return []


class ChangeScopeAnalyzer:
    @staticmethod
    def load(project_id: str) -> dict[str, Any] | None:
        path = _scope_path(project_id)
        if not path.exists():
            return None
        data = _read_json(path)
        return data or None

    @staticmethod
    def save(project_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
        path = _scope_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        analysis["schema_version"] = CHANGE_SCOPE_SCHEMA_VERSION
        analysis["project_id"] = project_id
        analysis["updated_at"] = _utc_now()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return analysis

    @staticmethod
    def analyze(
        project_id: str,
        prompt: str,
        project_state: dict[str, Any] | None = None,
        project_action: dict[str, Any] | None = None,
        workspace_awareness: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = project_state if project_state is not None else ProjectMemory.get_project_state(project_id)
        action = project_action if project_action is not None else ProjectMemory.classify_action(project_id, prompt)
        project_type = (state or {}).get("project_type") or "unknown"
        preserve_features = list((state or {}).get("features") or [])
        change_type, affected_areas = _classify_change_type(prompt)
        target_files = _select_target_files(change_type, workspace_awareness)
        size, impact_reason, confidence = _scope_size(
            change_type,
            prompt,
            target_files,
            bool(action and action.get("has_existing_project")),
        )
        questions = _clarifying_questions(change_type, size, prompt, project_type)
        validation = _required_validation(change_type, size, workspace_awareness)
        preserved_source_facts = _extract_preserved_source_facts(prompt, change_type, target_files, workspace_awareness)
        affected_count = max(
            len(target_files),
            int(((workspace_awareness or {}).get("impact_analysis") or {}).get("affected_count") or 0),
        )
        should_ask = bool(questions and size in {"medium", "large", "unclear"})

        analysis = {
            "schema_version": CHANGE_SCOPE_SCHEMA_VERSION,
            "project_id": project_id,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "request": prompt,
            "mode": (action or {}).get("action") or "unknown",
            "project_type": project_type,
            "change_type": change_type,
            "scope_size": size,
            "impact_reason": impact_reason,
            "changed_intent": re.sub(r"\s+", " ", (prompt or "").strip())[:220],
            "affected_areas": affected_areas,
            "target_files": target_files,
            "estimated_affected_files": affected_count,
            "preserve_features": preserve_features,
            "preserved_source_facts": preserved_source_facts,
            "preservation_constraints": [
                "Keep current source behavior and styling unless explicitly requested otherwise.",
                "Do not replace a whole file for small MODIFY scope when an insert/replace_block can satisfy the request.",
                *[
                    f"Must preserve: {fact}"
                    for fact in preserved_source_facts.get("relevant_preservation_facts", [])[:8]
                ],
            ],
            "required_validation": validation,
            "clarifying_questions": questions,
            "should_ask_clarification": should_ask,
            "safe_to_patch_locally": size == "small" and not should_ask,
            "confidence": confidence,
            "epistemic_rule": "This is a confidence-based impact estimate, not absolute truth.",
        }
        return ChangeScopeAnalyzer.save(project_id, analysis)

    @staticmethod
    def build_context(project_id: str, prompt: str, analysis: dict[str, Any] | None = None) -> str:
        scope = analysis or ChangeScopeAnalyzer.load(project_id) or ChangeScopeAnalyzer.analyze(project_id, prompt)
        return (
            "=== CHANGE SCOPE ANALYSIS ===\n"
            "Epistemic rule: impact classification is confidence-based, not absolute truth.\n"
            f"Mode: {scope.get('mode')} (scope={scope.get('scope_size')}, confidence={float(scope.get('confidence') or 0):.2f})\n"
            f"Change type: {scope.get('change_type')}\n"
            f"Changed intent: {scope.get('changed_intent')}\n"
            f"Affected areas: {', '.join(scope.get('affected_areas') or []) or 'none'}\n"
            f"Target files: {', '.join(scope.get('target_files') or []) or 'not confidently identified'}\n"
            f"Preserve features: {', '.join(scope.get('preserve_features') or []) or 'none recorded'}\n"
            f"Preserve source facts: {'; '.join((scope.get('preserved_source_facts') or {}).get('relevant_preservation_facts') or []) or 'none detected'}\n"
            f"Required validation: {', '.join(scope.get('required_validation') or []) or 'source_check'}\n"
            "Rules:\n"
            "- Small MODIFY scope means patch only the smallest affected files.\n"
            "- Preserve existing project state and visual/data decisions unless the request explicitly changes them.\n"
            "- Preservation constraints are mandatory guardrails for small MODIFY prompts.\n"
            "- For medium/large/unclear scope, ask narrowing questions before generating a broad plan.\n"
            "=== END CHANGE SCOPE ANALYSIS ==="
        )
