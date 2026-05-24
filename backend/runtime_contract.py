import json
from enum import Enum
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PROJECT_ROOT / "frontend" / "src" / "runtime" / "execution_contract.json"


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


EXECUTION_CONTRACT = _load_contract()


class ExecutionState(str, Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    PLANNING = "PLANNING"
    SCAFFOLDING = "SCAFFOLDING"
    GENERATING = "GENERATING"
    WRITING = "WRITING"
    VALIDATING = "VALIDATING"
    INSTALLING = "INSTALLING"
    BUILDING = "BUILDING"
    VERIFYING = "VERIFYING"
    STARTING_PREVIEW = "STARTING_PREVIEW"
    PREVIEW_READY = "PREVIEW_READY"
    REPAIRING = "REPAIRING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"


class RuntimeErrorCode(str, Enum):
    E_TS_REFERENCE_INVALID = "E_TS_REFERENCE_INVALID"
    E_IMPORT_RESOLUTION = "E_IMPORT_RESOLUTION"
    E_VITE_CONFIG = "E_VITE_CONFIG"
    E_REACT_ROOT_MISSING = "E_REACT_ROOT_MISSING"
    E_RUNTIME_BLANK = "E_RUNTIME_BLANK"
    E_DEPENDENCY_MISSING = "E_DEPENDENCY_MISSING"
    E_BUILD_FAILURE = "E_BUILD_FAILURE"
    E_PREVIEW_UNREACHABLE = "E_PREVIEW_UNREACHABLE"
    E_CONTRACT_INVALID = "E_CONTRACT_INVALID"


LEGACY_STATE_ALIASES: dict[str, str] = EXECUTION_CONTRACT["legacyStateAliases"]
STATE_TRANSITIONS: dict[str, list[str]] = EXECUTION_CONTRACT["transitions"]
ERROR_CODES: dict[str, dict[str, str]] = EXECUTION_CONTRACT["errorCodes"]
DEPENDENCY_POLICY: dict[str, Any] = EXECUTION_CONTRACT["dependencyPolicy"]


def normalize_execution_state(state: str | ExecutionState) -> ExecutionState:
    raw = state.value if isinstance(state, ExecutionState) else str(state)
    normalized = LEGACY_STATE_ALIASES.get(raw, raw)
    if normalized not in EXECUTION_CONTRACT["states"]:
        raise ValueError(f"Unknown execution state: {state!r}")
    return ExecutionState(normalized)


def normalize_error_code(code: str | RuntimeErrorCode) -> RuntimeErrorCode:
    raw = code.value if isinstance(code, RuntimeErrorCode) else str(code)
    if raw not in ERROR_CODES:
        return RuntimeErrorCode.E_BUILD_FAILURE
    return RuntimeErrorCode(raw)


def can_transition(from_state: str | ExecutionState, to_state: str | ExecutionState) -> bool:
    source = normalize_execution_state(from_state).value
    target = normalize_execution_state(to_state).value
    return target in STATE_TRANSITIONS.get(source, [])


def error_payload(
    code: str | RuntimeErrorCode,
    message: str,
    *,
    project_id: str | None = None,
    run_id: str | None = None,
    source: str = "runtime",
) -> dict[str, str | None]:
    normalized = normalize_error_code(code)
    meta = ERROR_CODES[normalized.value]
    return {
        "code": normalized.value,
        "category": meta["category"],
        "message": message,
        "project_id": project_id,
        "run_id": run_id,
        "source": source,
    }


def classify_dependency_import(package_name: str, declared_packages: set[str]) -> RuntimeErrorCode | None:
    if package_name in DEPENDENCY_POLICY["blockedDependencies"]:
        return RuntimeErrorCode.E_DEPENDENCY_MISSING
    if package_name in declared_packages:
        return None
    if package_name in DEPENDENCY_POLICY["allowedDependencies"]:
        return None
    return RuntimeErrorCode(DEPENDENCY_POLICY["undeclaredImportCode"])
