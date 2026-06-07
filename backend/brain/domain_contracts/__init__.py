import re
from typing import Any

from backend.brain.domain_contract_registry import (
    clear_contract_cache,
    load_all_contracts,
    load_contract,
)


def load_contracts() -> dict[str, dict[str, Any]]:
    return load_all_contracts()


def get_contract(app_type: str) -> dict[str, Any] | None:
    try:
        return load_contract(app_type)
    except Exception:
        return None


def get_all_contracts() -> list[dict[str, Any]]:
    return list(load_all_contracts().values())


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
    return bool(re.search(rf"\b{re.escape(word)}\b", prompt_lower))


def get_broad_match_type(prompt: str) -> str | None:
    prompt_lower = (prompt or "").lower()
    prompt_clean = re.sub(r"[^a-z0-9\s]", " ", prompt_lower)
    words = prompt_clean.split()

    contracts = load_all_contracts()
    for app_type, contract in contracts.items():
        for keyword in contract.get("keywords", []):
            if _has_word(prompt_lower, str(keyword).lower()):
                return app_type

    for app_type, contract in contracts.items():
        for word in words:
            if len(word) < 5:
                continue
            for keyword_raw in contract.get("keywords", []):
                keyword = str(keyword_raw).lower()
                if len(keyword) < 5 or abs(len(word) - len(keyword)) > 2:
                    continue
                max_dist = 2 if len(keyword) < 8 else 3
                if _levenshtein_distance(word, keyword) <= max_dist:
                    return app_type

    return None


__all__ = [
    "clear_contract_cache",
    "get_all_contracts",
    "get_broad_match_type",
    "get_contract",
    "load_contract",
    "load_contracts",
]
