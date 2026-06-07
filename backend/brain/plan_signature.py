import re
from typing import Any

from backend.brain.contract_discovery import discover_contract
from backend.brain.schemas import ComplexityLevel, PlanSignature
from backend.brain.prompt_cleaning import clean_user_intent_prompt


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _levenshtein_distance(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]


def _has_word(prompt_lower: str, word: str) -> bool:
    return bool(re.search(rf'\b{re.escape(word)}\b', prompt_lower))


def _get_broad_match_type(prompt: str) -> str | None:
    discovered = discover_contract(prompt)
    if discovered.contract is None:
        return None
    return str(discovered.contract.get("app_type") or "")


CRUD_TERMS = ["crud", "create read update delete"]
CRUD_ENTITIES = [
    "todo",
    "task",
    "produk",
    "product",
    "barang",
    "item",
    "user",
    "customer",
    "employee",
    "student",
    "book",
    "order",
    "transaction",
    "transaksi",
]
CRUD_STORAGE_TERMS = [
    "local storage",
    "localstorage",
    "sql",
    "mysql",
    "postgres",
    "sqlite",
    "database",
    "db",
    "json",
    "backend",
    "api",
]


def _has_crud(text: str) -> bool:
    return _contains_any(text, CRUD_TERMS)


def _has_crud_entity(text: str) -> bool:
    return _contains_any(text, CRUD_ENTITIES)


def _has_crud_storage(text: str) -> bool:
    return _contains_any(text, CRUD_STORAGE_TERMS)


def _complexity_from_contract(contract: dict[str, Any]) -> ComplexityLevel:
    raw_value = str(contract.get("complexity_default") or ComplexityLevel.MEDIUM.value).lower()
    try:
        return ComplexityLevel(raw_value)
    except ValueError:
        return ComplexityLevel.MEDIUM


def build_plan_signature(prompt: str) -> PlanSignature:
    prompt = clean_user_intent_prompt(prompt)
    text = prompt.strip().lower()
    intent = "build_app" if _contains_any(text, ["buat", "build", "create", "make", "aplikasi", "app", "crud"]) else "unknown"

    discovered = discover_contract(prompt)
    if discovered.contract is not None:
        contract = discovered.contract
        return PlanSignature(
            domain=str(contract.get("domain") or contract.get("app_type") or "UNKNOWN_DOMAIN"),
            intent=intent,
            app_type=str(contract.get("app_type") or "unknown_domain"),
            complexity=_complexity_from_contract(contract),
            feature_keywords=_unique(list(contract.get("feature_keywords") or contract.get("features") or [])),
            required_capabilities=_unique(
                list(contract.get("required_capabilities") or contract.get("capabilities") or [])
            ),
        )

    domain = "UNKNOWN_DOMAIN"
    app_type = "unknown_domain"
    complexity = ComplexityLevel.MEDIUM
    feature_keywords: list[str] = []
    required_capabilities: list[str] = ["state_management"]

    # LEGACY_FALLBACK: retained for backward compatibility with simple utility
    # signatures that are not domain contracts.
    if _contains_any(text, ["hello world", "halo dunia"]):
        domain = "utility"
        app_type = "hello_world"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["hello_world"]
        required_capabilities = ["static_rendering"]
    elif _contains_any(text, ["login", "auth", "authentication", "register"]):
        domain = "auth"
        app_type = "auth_app"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["auth", "login", "session"]
        required_capabilities = ["state_management", "data_persistence", "backend_api", "authentication"]
    elif _contains_any(text, ["database", "db", "sql", "mysql", "postgres", "sqlite"]):
        domain = "data"
        app_type = "data_app"
        complexity = ComplexityLevel.HIGH
        feature_keywords = ["database", "persistence"]
        required_capabilities = ["state_management", "data_persistence"]
    elif _contains_any(text, ["todo", "to-do", "task list"]):
        domain = "utility"
        app_type = "todo"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["tasks"]
        required_capabilities = ["crud", "state_management"]
    elif _contains_any(text, ["counter", "penghitung"]):
        domain = "utility"
        app_type = "counter"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["counter"]
        required_capabilities = ["state_management"]
    elif _contains_any(text, ["calculator", "kalkulator"]):
        domain = "utility"
        app_type = "calculator"
        complexity = ComplexityLevel.LOW
        feature_keywords = ["calculator"]
        required_capabilities = ["state_management"]

    # LEGACY_FALLBACK: enrich only compatibility signatures, never contract
    # signatures, because contracts are the source of truth.
    if app_type != "unknown_domain" and _contains_any(text, ["admin"]) and "admin" not in feature_keywords:
        feature_keywords.append("admin")
    if app_type != "unknown_domain" and _has_crud(text) and "crud" not in required_capabilities:
        required_capabilities.append("crud")
    if (
        app_type != "unknown_domain"
        and _contains_any(text, ["database", "db", "persist", "simpan data"])
        and "data_persistence" not in required_capabilities
    ):
        required_capabilities.append("data_persistence")

    return PlanSignature(
        domain=domain,
        intent=intent,
        app_type=app_type,
        complexity=complexity,
        feature_keywords=_unique(feature_keywords),
        required_capabilities=_unique(required_capabilities),
    )
