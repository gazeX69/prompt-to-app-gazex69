import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from backend.brain.domain_contract_registry import load_all_contracts


@dataclass(frozen=True)
class ContractDiscoveryResult:
    contract: dict[str, Any] | None
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", ascii_text.lower())).strip()


def _contains_keyword(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])", text.lower()))


def _levenshtein_distance(first: str, second: str) -> int:
    if len(first) < len(second):
        return _levenshtein_distance(second, first)
    if not second:
        return len(first)

    previous_row = range(len(second) + 1)
    for i, char_first in enumerate(first):
        current_row = [i + 1]
        for j, char_second in enumerate(second):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (char_first != char_second)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _typo_tolerance(keyword: str) -> int:
    if len(keyword) < 5:
        return 0
    return 2 if len(keyword) < 8 else 3


def _has_light_typo_match(prompt_words: list[str], keyword: str) -> bool:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword or " " in normalized_keyword:
        return False

    tolerance = _typo_tolerance(normalized_keyword)
    if tolerance == 0:
        return False

    for word in prompt_words:
        if len(word) < 5 or abs(len(word) - len(normalized_keyword)) > tolerance:
            continue
        if _levenshtein_distance(word, normalized_keyword) <= tolerance:
            return True
    return False


def _score_contract(prompt: str, normalized_prompt: str, contract: dict[str, Any]) -> tuple[float, list[str]]:
    keywords = [str(keyword) for keyword in contract.get("keywords") or [] if str(keyword).strip()]
    prompt_words = normalized_prompt.split()
    matched_keywords: list[str] = []
    score = 0.0

    for keyword in keywords:
        if _contains_keyword(prompt, keyword):
            matched_keywords.append(keyword)
            score = max(score, 1.0)

    for keyword in keywords:
        normalized_keyword = _normalize_text(keyword)
        if normalized_keyword and _contains_keyword(normalized_prompt, normalized_keyword):
            matched_keywords.append(keyword)
            score = max(score, 0.9)

    for keyword in keywords:
        if _has_light_typo_match(prompt_words, keyword):
            matched_keywords.append(keyword)
            score = max(score, 0.75)

    return score, _unique(matched_keywords)


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def discover_contract(prompt: str) -> ContractDiscoveryResult:
    normalized_prompt = _normalize_text(prompt)
    best_contract: dict[str, Any] | None = None
    best_confidence = 0.0
    best_keywords: list[str] = []

    for app_type, contract in sorted(load_all_contracts().items()):
        confidence, matched_keywords = _score_contract(prompt, normalized_prompt, contract)
        if confidence > best_confidence:
            best_contract = contract
            best_confidence = confidence
            best_keywords = matched_keywords
        elif confidence == best_confidence and confidence > 0 and best_contract is not None:
            current_key = str(contract.get("app_type") or app_type)
            best_key = str(best_contract.get("app_type") or "")
            if current_key < best_key:
                best_contract = contract
                best_keywords = matched_keywords

    return ContractDiscoveryResult(
        contract=best_contract,
        confidence=best_confidence,
        matched_keywords=best_keywords,
    )
