import copy
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONTRACT_VERSION = "v1"
CONTRACTS_DIR = Path(__file__).resolve().parent / "domain_contracts"
_CONTRACT_CACHE: dict[str, dict[str, Any]] = {}


class DomainContractError(RuntimeError):
    pass


def _normalize_contract(raw: dict[str, Any], fallback_app_type: str) -> dict[str, Any]:
    contract = copy.deepcopy(raw)
    app_type = str(contract.get("app_type") or fallback_app_type).strip()
    if not app_type:
        raise DomainContractError("Domain contract is missing app_type.")

    contract["app_type"] = app_type
    contract.setdefault("contract_version", CONTRACT_VERSION)
    contract.setdefault("version", contract["contract_version"])
    contract.setdefault("keywords", [])
    contract.setdefault("features", contract.get("feature_keywords", []))
    contract.setdefault("feature_keywords", contract.get("features", []))
    contract.setdefault("capabilities", contract.get("required_capabilities", []))
    contract.setdefault("required_capabilities", contract.get("capabilities", []))
    contract.setdefault("decisions", contract.get("decision_keys", []))
    contract.setdefault("decision_keys", contract.get("decisions", []))
    contract.setdefault("mvp_features", contract.get("recommended_mvp_features", []))
    contract.setdefault("recommended_mvp_features", contract.get("mvp_features", []))
    contract.setdefault("validation_rules", {})
    return contract


def _contract_path(app_type: str) -> Path:
    safe_name = app_type.strip().lower().replace("-", "_")
    if not safe_name or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_" for char in safe_name):
        raise DomainContractError(f"Invalid domain contract key: {app_type!r}")
    return CONTRACTS_DIR / f"{safe_name}.json"


def _emit_contract_trace(contract: dict[str, Any]) -> None:
    features = contract.get("features") or contract.get("feature_keywords") or []
    logger.info("[ContractRegistry] Kontrak yang dimuat: %s", contract.get("app_type"))
    logger.info("[ContractRegistry] Versi kontrak: %s", contract.get("contract_version") or contract.get("version"))
    logger.info("[ContractRegistry] Fitur: %s", ", ".join(str(item) for item in features))


def load_contract(app_type: str) -> dict[str, Any]:
    key = app_type.strip().lower().replace("-", "_")
    if key in _CONTRACT_CACHE:
        contract = copy.deepcopy(_CONTRACT_CACHE[key])
        _emit_contract_trace(contract)
        return contract

    path = _contract_path(key)
    if not path.exists():
        raise DomainContractError(f"Domain contract not found: {key}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DomainContractError(f"Invalid domain contract JSON: {path.name}") from exc

    contract = _normalize_contract(raw, key)
    _CONTRACT_CACHE[key] = contract
    _emit_contract_trace(contract)
    return copy.deepcopy(contract)


def load_all_contracts() -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(CONTRACTS_DIR.glob("*.json")):
        contract = load_contract(path.stem)
        contracts[contract["app_type"]] = contract
    return contracts


def clear_contract_cache() -> None:
    _CONTRACT_CACHE.clear()


def get_contract_keywords(app_type: str) -> list[str]:
    return list(load_contract(app_type).get("keywords") or [])


def get_contract_features(app_type: str) -> list[str]:
    return list(load_contract(app_type).get("features") or [])


def get_contract_capabilities(app_type: str) -> list[str]:
    return list(load_contract(app_type).get("capabilities") or [])


def get_contract_decisions(app_type: str) -> list[str]:
    return list(load_contract(app_type).get("decisions") or [])


def get_contract_mvp_features(app_type: str) -> list[str]:
    return list(load_contract(app_type).get("mvp_features") or [])


def get_contract_validation_rules(app_type: str) -> dict[str, Any]:
    return dict(load_contract(app_type).get("validation_rules") or {})
