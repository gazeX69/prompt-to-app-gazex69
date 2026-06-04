import math
import re
from collections import Counter
from backend.brain.memory_store import load_cases, load_failures
from backend.brain.schemas import CaseMemory, MatchedCase, PlanSignature


def calculate_cosine_similarity(text1: str, text2: str) -> float:
    """Calculate simple token-based bag-of-words cosine similarity between two texts."""
    def get_tokens(text):
        return re.findall(r'\w+', text.lower())

    words1 = get_tokens(text1)
    words2 = get_tokens(text2)

    if not words1 or not words2:
        return 0.0

    vec1 = Counter(words1)
    vec2 = Counter(words2)

    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])

    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    return float(numerator) / denominator


def _overlap_score(left: list[str], right: list[str]) -> float:
    """Compute standard Jaccard overlap similarity coefficient between two feature sets."""
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _failure_penalty(signature: PlanSignature) -> float:
    penalty = 0.0
    for item in load_failures():
        if item.get("domain") == signature.domain or item.get("app_type") == signature.app_type:
            avoided = item.get("avoided_capabilities") if isinstance(item.get("avoided_capabilities"), list) else []
            if set(avoided) & set(signature.required_capabilities):
                penalty += 0.05
    return min(penalty, 0.15)


def retrieve_matching_cases(signature: PlanSignature, prompt: str = None, limit: int = 3) -> list[MatchedCase]:
    """
    Retrieve case history memories matching the signature and prompt query.
    Employs Jaccard Weighted Structural Similarity blended with textual Cosine Semantic Similarity.
    """
    matches: list[MatchedCase] = []
    penalty = _failure_penalty(signature)

    for item in load_cases():
        try:
            case = CaseMemory(**item)
        except Exception:
            continue

        # 1. Jaccard Weighted Structural Similarity (Bobot: Domain=5, AppType=4, Features=3, Caps=2)
        sim_domain = 1.0 if case.domain == signature.domain else 0.0
        sim_app_type = 1.0 if case.app_type == signature.app_type else 0.0
        sim_features = _overlap_score(case.feature_keywords, signature.feature_keywords)
        sim_caps = _overlap_score(case.required_capabilities, signature.required_capabilities)

        score_structural = ((5.0 * sim_domain) + (4.0 * sim_app_type) + (3.0 * sim_features) + (2.0 * sim_caps)) / 14.0

        # 2. Textual Cosine Similarity (Compare prompt with case text index)
        cosine_score = 0.0
        if prompt:
            # Build search index context
            case_text = f"{case.title or ''} {case.summary or ''} {case.original_prompt or ''}"
            cosine_score = calculate_cosine_similarity(prompt, case_text)
            # Blend Score: 60% Weighted Structural + 40% Textual Cosine Similarity
            score = 0.60 * score_structural + 0.40 * cosine_score
        else:
            score = score_structural

        # Deduct penalties
        score = max(0.0, min(1.0, score - penalty))

        if score >= 0.15:
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
                    original_prompt=case.original_prompt,
                    context=case.context,
                    constraints=case.constraints,
                    solution=case.solution,
                    lessons_learned=case.lessons_learned,
                    structural_score=round(score_structural, 2),
                    cosine_score=round(cosine_score, 2)
                )
            )

    matches.sort(key=lambda match: match.score, reverse=True)
    return matches[:limit]

