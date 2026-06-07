from datetime import datetime, timezone
import json
import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.agent.tools import _safe_project_path

logger = logging.getLogger(__name__)

REFLECTION_SCHEMA_VERSION = "p11.reflection_engine.v1"
REFLECTION_RELATIVE_PATH = ".ai-agent/reflection_engine.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _artifact_path(project_id: str) -> Path:
    return _safe_project_path(project_id) / REFLECTION_RELATIVE_PATH


def _combined_text(stdout: str | None, stderr: str | None, error: str | None = None) -> str:
    return "\n".join(part or "" for part in [stdout, stderr, error])


def _tail(value: str | None, limit: int = 4000) -> str:
    value = value or ""
    return value[-limit:]


class ReflectionEngine:
    @staticmethod
    def load(project_id: str) -> dict[str, Any]:
        path = _artifact_path(project_id)
        if not path.exists():
            return ReflectionEngine._empty(project_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ReflectionEngine._empty(project_id)
        return data if isinstance(data, dict) else ReflectionEngine._empty(project_id)

    @staticmethod
    def save(project_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
        path = _artifact_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        artifact["schema_version"] = REFLECTION_SCHEMA_VERSION
        artifact["project_id"] = project_id
        artifact["updated_at"] = _utc_now()
        artifact["reflection_score"] = ReflectionEngine.compute_score(artifact)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return artifact

    @staticmethod
    def _empty(project_id: str) -> dict[str, Any]:
        now = _utc_now()
        return {
            "schema_version": REFLECTION_SCHEMA_VERSION,
            "project_id": project_id,
            "created_at": now,
            "updated_at": now,
            "last_component": None,
            "maturity": {
                "level_1_validation_engine": False,
                "level_2_error_collector": False,
                "level_3_root_cause_analyzer": False,
                "level_4_repair_planner": False,
                "level_5_repair_executor": False,
                "level_6_revalidation_engine": False,
                "level_7_learning_capture": False,
                "predictive_reflection": False,
            },
            "cycles": [],
            "learning": [],
            "reflection_score": {"score": 0, "grade": "unknown", "components": {}},
        }

    @staticmethod
    def compute_score(artifact: dict[str, Any]) -> dict[str, Any]:
        cycles = artifact.get("cycles") or []
        latest = cycles[-1] if cycles else {}
        validation = latest.get("validation") or {}
        revalidation = latest.get("revalidation") or {}
        maturity = artifact.get("maturity") or {}
        components = {
            "build_validation": 30 if validation.get("status") == "passed" or revalidation.get("status") == "passed" else 0,
            "error_diagnosis": 20 if maturity.get("level_3_root_cause_analyzer") else 0,
            "repair_execution": 20 if (latest.get("repair_execution") or {}).get("success") else 0,
            "revalidation": 20 if revalidation.get("status") == "passed" else 0,
            "learning": 10 if maturity.get("level_7_learning_capture") else 0,
        }
        score = sum(components.values())
        if not cycles and maturity.get("predictive_reflection"):
            score = 10
        grade = "excellent" if score >= 90 else "good" if score >= 70 else "partial" if score >= 40 else "needs_attention"
        return {"score": score, "grade": grade, "components": components}

    @staticmethod
    def start_cycle(project_id: str, run_id: str | None, stage: str, command: str | None = None) -> dict[str, Any]:
        artifact = ReflectionEngine.load(project_id)
        cycle = {
            "id": f"refl_{uuid4().hex[:10]}",
            "run_id": run_id,
            "stage": stage,
            "command": command,
            "started_at": _utc_now(),
            "status": "running",
            "validation": None,
            "errors": [],
            "root_cause": None,
            "repair_plan": [],
            "repair_execution": None,
            "revalidation": None,
            "learning": None,
        }
        artifact["cycles"].append(cycle)
        artifact["last_component"] = "validation_engine"
        artifact["maturity"]["level_1_validation_engine"] = True
        ReflectionEngine.save(project_id, artifact)
        return cycle

    @staticmethod
    def latest_cycle(project_id: str, run_id: str | None = None) -> dict[str, Any] | None:
        artifact = ReflectionEngine.load(project_id)
        cycles = artifact.get("cycles") or []
        if run_id:
            cycles = [cycle for cycle in cycles if cycle.get("run_id") == run_id]
        return cycles[-1] if cycles else None

    @staticmethod
    def _update_cycle(project_id: str, cycle_id: str, update: dict[str, Any], last_component: str, maturity_key: str) -> dict[str, Any]:
        artifact = ReflectionEngine.load(project_id)
        for cycle in artifact.get("cycles") or []:
            if cycle.get("id") == cycle_id:
                cycle.update(update)
                break
        artifact["last_component"] = last_component
        artifact["maturity"][maturity_key] = True
        return ReflectionEngine.save(project_id, artifact)

    @staticmethod
    def record_validation(project_id: str, run_id: str | None, stage: str, command_result, command: str | None = None) -> dict[str, Any]:
        cycle = ReflectionEngine.start_cycle(project_id, run_id, stage, command or getattr(command_result, "command", None))
        validation = {
            "status": "passed" if getattr(command_result, "success", False) else "failed",
            "stage": stage,
            "command": command or getattr(command_result, "command", None),
            "exit_code": getattr(command_result, "exit_code", None),
            "stdout_tail": _tail(getattr(command_result, "stdout", "")),
            "stderr_tail": _tail(getattr(command_result, "stderr", "")),
            "error": getattr(command_result, "error", None),
            "observed_at": _utc_now(),
        }
        ReflectionEngine._update_cycle(
            project_id,
            cycle["id"],
            {"validation": validation, "status": "validated" if validation["status"] == "passed" else "failed"},
            "validation_engine",
            "level_1_validation_engine",
        )
        if validation["status"] == "failed":
            errors = ReflectionEngine.collect_errors(validation)
            root_cause = ReflectionEngine.analyze_root_cause(errors, validation)
            repair_plan = ReflectionEngine.plan_repair(root_cause, validation)
            ReflectionEngine.attach_errors_analysis_plan(project_id, cycle["id"], errors, root_cause, repair_plan)
        return validation

    @staticmethod
    def collect_errors(validation: dict[str, Any]) -> list[dict[str, Any]]:
        text = _combined_text(validation.get("stdout_tail"), validation.get("stderr_tail"), validation.get("error"))
        errors: list[dict[str, Any]] = []

        for match in re.finditer(r"\b(TS\d{4})\b[:\s-]*(.+)", text):
            errors.append({
                "type": "typescript",
                "code": match.group(1),
                "message": match.group(2).strip()[:500],
                "confidence": 0.9,
            })

        module_match = re.search(r"(?:cannot find module|failed to resolve import|module not found|cannot resolve)\s+['\"]?([^'\"\s]+)", text, re.IGNORECASE)
        if module_match:
            errors.append({
                "type": "import_resolution",
                "code": "MODULE_NOT_FOUND",
                "message": module_match.group(0)[:500],
                "package": module_match.group(1),
                "confidence": 0.94,
            })

        file_match = re.search(r"([\w./\\-]+\.(?:tsx?|jsx?|py|php|json|css))", text)
        if file_match and errors:
            for error in errors:
                error.setdefault("file", file_match.group(1).replace("\\", "/"))

        if not errors and text.strip():
            errors.append({
                "type": "unknown",
                "code": "UNKNOWN_ERROR",
                "message": text.strip()[:700],
                "confidence": 0.25,
            })
        return errors

    @staticmethod
    def analyze_root_cause(errors: list[dict[str, Any]], validation: dict[str, Any]) -> dict[str, Any]:
        text = _combined_text(validation.get("stdout_tail"), validation.get("stderr_tail"), validation.get("error")).lower()
        first = errors[0] if errors else {}
        category = "unknown"
        confidence = 0.25
        evidence: list[str] = []

        if first.get("type") == "import_resolution" or "cannot find module" in text or "failed to resolve import" in text:
            category = "missing_dependency_or_bad_import"
            confidence = 0.9
            evidence.append("Import/module resolution error detected.")
        if "ts2345" in text and ("setstateaction" in text or "assignable" in text):
            category = "nullable_or_partial_state"
            confidence = 0.88
            evidence.append("TypeScript state update produced nullable/partial type mismatch.")
        elif "tsconfig" in text or "ts6310" in text or "referenced project" in text:
            category = "typescript_config"
            confidence = 0.86
            evidence.append("TypeScript config/reference error detected.")
        elif "syntax error" in text or "unexpected token" in text or "transform failed" in text:
            category = "syntax_or_transform_error"
            confidence = 0.82
            evidence.append("Parser/transform failure detected.")
        elif "getelementbyid" in text or "createroot" in text or "#root" in text:
            category = "react_root_contract"
            confidence = 0.84
            evidence.append("React root/runtime contract issue detected.")
        elif "npm err" in text or "enoent" in text:
            category = "install_or_filesystem_error"
            confidence = 0.72
            evidence.append("Install/filesystem command failure detected.")

        return {
            "category": category,
            "confidence": confidence,
            "evidence": evidence or ["No high-confidence deterministic signature matched."],
            "primary_error": first,
        }

    @staticmethod
    def plan_repair(root_cause: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
        category = root_cause.get("category")
        plans_by_category = {
            "missing_dependency_or_bad_import": [
                {"solution": "replace_with_declared_dependency_or_local_code", "confidence": 0.82, "risk": "medium"},
                {"solution": "add_declared_dependency_then_reinstall", "confidence": 0.7, "risk": "medium"},
                {"solution": "remove_unused_import", "confidence": 0.55, "risk": "low"},
            ],
            "nullable_or_partial_state": [
                {"solution": "make_form_state_non_nullable", "confidence": 0.9, "risk": "low"},
                {"solution": "split_entity_type_and_form_type", "confidence": 0.86, "risk": "low"},
            ],
            "typescript_config": [
                {"solution": "restore_canonical_tsconfig_contract", "confidence": 0.88, "risk": "low"},
                {"solution": "add_missing_config_runtime_dependency", "confidence": 0.64, "risk": "medium"},
            ],
            "syntax_or_transform_error": [
                {"solution": "patch_syntax_near_reported_file", "confidence": 0.76, "risk": "medium"},
            ],
            "react_root_contract": [
                {"solution": "restore_react_vite_entrypoint_contract", "confidence": 0.88, "risk": "low"},
            ],
            "install_or_filesystem_error": [
                {"solution": "rerun_install_after_manifest_check", "confidence": 0.62, "risk": "medium"},
            ],
        }
        return plans_by_category.get(category, [{"solution": "llm_guided_targeted_patch", "confidence": 0.42, "risk": "medium"}])

    @staticmethod
    def attach_errors_analysis_plan(
        project_id: str,
        cycle_id: str,
        errors: list[dict[str, Any]],
        root_cause: dict[str, Any],
        repair_plan: list[dict[str, Any]],
    ) -> dict[str, Any]:
        artifact = ReflectionEngine.load(project_id)
        for cycle in artifact.get("cycles") or []:
            if cycle.get("id") == cycle_id:
                cycle["errors"] = errors
                cycle["root_cause"] = root_cause
                cycle["repair_plan"] = repair_plan
                break
        artifact["last_component"] = "repair_planner"
        artifact["maturity"].update({
            "level_2_error_collector": True,
            "level_3_root_cause_analyzer": True,
            "level_4_repair_planner": True,
        })
        return ReflectionEngine.save(project_id, artifact)

    @staticmethod
    def record_repair_execution(
        project_id: str,
        run_id: str | None,
        *,
        success: bool,
        attempt: int,
        patched_files: list[str] | None = None,
        package_json_modified: bool = False,
        message: str | None = None,
    ) -> dict[str, Any]:
        cycle = ReflectionEngine.latest_cycle(project_id, run_id)
        if not cycle:
            cycle = ReflectionEngine.start_cycle(project_id, run_id, "repair", "repair")
        execution = {
            "success": success,
            "attempt": attempt,
            "patched_files": patched_files or [],
            "package_json_modified": package_json_modified,
            "message": message,
            "executed_at": _utc_now(),
        }
        return ReflectionEngine._update_cycle(
            project_id,
            cycle["id"],
            {"repair_execution": execution},
            "repair_executor",
            "level_5_repair_executor",
        )

    @staticmethod
    def record_revalidation(project_id: str, run_id: str | None, command_result, stage: str = "build_revalidation") -> dict[str, Any]:
        cycle = ReflectionEngine.latest_cycle(project_id, run_id)
        if not cycle:
            cycle = ReflectionEngine.start_cycle(project_id, run_id, stage, getattr(command_result, "command", None))
        revalidation = {
            "status": "passed" if getattr(command_result, "success", False) else "failed",
            "stage": stage,
            "command": getattr(command_result, "command", None),
            "exit_code": getattr(command_result, "exit_code", None),
            "stdout_tail": _tail(getattr(command_result, "stdout", "")),
            "stderr_tail": _tail(getattr(command_result, "stderr", "")),
            "error": getattr(command_result, "error", None),
            "observed_at": _utc_now(),
        }
        ReflectionEngine._update_cycle(
            project_id,
            cycle["id"],
            {"revalidation": revalidation, "status": "resolved" if revalidation["status"] == "passed" else "unresolved"},
            "revalidation_engine",
            "level_6_revalidation_engine",
        )
        return ReflectionEngine.capture_learning(project_id, cycle["id"])

    @staticmethod
    def capture_learning(project_id: str, cycle_id: str) -> dict[str, Any]:
        artifact = ReflectionEngine.load(project_id)
        learning_record = None
        for cycle in artifact.get("cycles") or []:
            if cycle.get("id") != cycle_id:
                continue
            root = cycle.get("root_cause") or {}
            execution = cycle.get("repair_execution") or {}
            revalidation = cycle.get("revalidation") or {}
            learning_record = {
                "cycle_id": cycle_id,
                "problem": (cycle.get("errors") or [{}])[0].get("code", "UNKNOWN"),
                "root_cause": root.get("category", "unknown"),
                "root_cause_confidence": root.get("confidence", 0.0),
                "repair": execution.get("message") or ", ".join(execution.get("patched_files") or []) or "none",
                "outcome": revalidation.get("status") or ("patched" if execution.get("success") else "failed"),
                "captured_at": _utc_now(),
            }
            cycle["learning"] = learning_record
            break
        if learning_record:
            artifact.setdefault("learning", []).append(learning_record)
        artifact["last_component"] = "learning_capture"
        artifact["maturity"]["level_7_learning_capture"] = True
        return ReflectionEngine.save(project_id, artifact)

    @staticmethod
    def predictive_reflection(project_id: str, prompt: str, workspace_awareness: dict[str, Any] | None = None) -> dict[str, Any]:
        project_state = None
        try:
            from backend.memory.project_memory import ProjectMemory

            project_state = ProjectMemory.load_for(project_id, "reflection")
            logger.info("[ProjectState] Loaded for reflection")
        except Exception:
            project_state = None
        impact = (workspace_awareness or {}).get("impact_analysis") or {}
        risk = impact.get("risk") or "unknown"
        prediction = {
            "prompt": prompt,
            "project_state": {
                "project_type": (project_state or {}).get("project_type", "unknown"),
                "domain": (project_state or {}).get("domain"),
                "database": (project_state or {}).get("database"),
                "supplier": (project_state or {}).get("supplier"),
            },
            "risk": risk,
            "confidence": impact.get("confidence", 0.35),
            "affected_files": impact.get("affected_files", []),
            "message": f"Predicted mutation risk is {risk}.",
            "created_at": _utc_now(),
        }
        artifact = ReflectionEngine.load(project_id)
        artifact["predictive_reflection"] = prediction
        artifact["maturity"]["predictive_reflection"] = True
        artifact["last_component"] = "predictive_reflection"
        ReflectionEngine.save(project_id, artifact)
        return prediction
