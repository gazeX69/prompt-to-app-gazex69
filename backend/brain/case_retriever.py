from backend.brain.memory_store import load_cases, load_failures
from backend.brain.schemas import CaseMemory, MatchedCase, PlanSignature


def _overlap_score(left: list[str], right: list[str], weight: float) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return weight * (len(left_set & right_set) / len(left_set | right_set))


def _failure_penalty(signature: PlanSignature) -> float:
    penalty = 0.0
    for item in load_failures():
        if item.get("domain") == signature.domain or item.get("app_type") == signature.app_type:
            avoided = item.get("avoided_capabilities") if isinstance(item.get("avoided_capabilities"), list) else []
            if set(avoided) & set(signature.required_capabilities):
                penalty += 0.05
    return min(penalty, 0.15)


def retrieve_matching_cases(signature: PlanSignature, limit: int = 3) -> list[MatchedCase]:
    matches: list[MatchedCase] = []
    penalty = _failure_penalty(signature)

    for item in load_cases():
        try:
            case = CaseMemory(**item)
        except Exception:
            continue

        score = 0.0
        if case.domain == signature.domain:
            score += 0.35
        if case.app_type == signature.app_type:
            score += 0.35
        score += _overlap_score(case.feature_keywords, signature.feature_keywords, 0.15)
        score += _overlap_score(case.required_capabilities, signature.required_capabilities, 0.15)
        score = max(0.0, min(1.0, score - penalty))

        if score >= 0.2:
            matches.append(
                MatchedCase(
                    id=case.id,
                    title=case.title,
                    domain=case.domain,
                    app_type=case.app_type,
                    score=round(score, 2),
                    feature_keywords=case.feature_keywords,
                    required_capabilities=case.required_capabilities,
                    summary=case.summary,
                )
            )

    matches.sort(key=lambda match: match.score, reverse=True)
    return matches[:limit]
