from backend.brain.schemas import (
    BrainDecision,
    BrainDecisionResult,
    ComplexityLevel,
    MatchedCase,
    PlanSignature,
    RecommendedMVP,
    RiskLevel,
    ScopeAnalysis,
)


def _recommended_mvp(signature: PlanSignature) -> RecommendedMVP:
    if signature.app_type == "marketplace":
        return RecommendedMVP(
            title="Marketplace MVP",
            features=[
                "Product listing",
                "Product detail",
                "Cart",
                "Simulated checkout",
                "Simple admin product CRUD",
            ],
        )
    if signature.app_type == "inventory":
        return RecommendedMVP(
            title="Inventory MVP",
            features=[
                "Item list",
                "Add/edit/delete item",
                "Stock quantity tracking",
                "Low stock indicator",
                "Simple local persistence",
            ],
        )
    if signature.app_type == "counter":
        return RecommendedMVP(
            title="Counter App",
            features=["Increment", "Decrement", "Reset"],
        )
    if signature.app_type == "todo":
        return RecommendedMVP(
            title="Todo App",
            features=["Task list", "Add task", "Mark complete", "Delete task"],
        )
    if signature.app_type == "calculator":
        return RecommendedMVP(
            title="Calculator App",
            features=["Number input", "Basic operations", "Clear result"],
        )
    return RecommendedMVP(
        title=f"{signature.app_type.replace('-', ' ').title()} MVP",
        features=["Core list view", "Primary detail view", "Simple local state"],
    )


def _requires_fresh_external_knowledge(prompt: str) -> bool:
    text = prompt.lower()
    return any(
        term in text
        for term in [
            "data terbaru",
            "latest",
            "terkini",
            "real market data",
            "regulasi terbaru",
            "current prices",
        ]
    )


def decide_preflight(
    prompt: str,
    signature: PlanSignature,
    scope_analysis: ScopeAnalysis,
    matched_cases: list[MatchedCase],
) -> BrainDecisionResult:
    recommended_mvp = _recommended_mvp(signature)

    if _requires_fresh_external_knowledge(prompt):
        return BrainDecisionResult(
            decision=BrainDecision.PROVIDER_REQUIRED,
            confidence=0.72,
            reason="Prompt explicitly requires fresh external/domain knowledge that local deterministic preflight cannot verify.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    if signature.complexity == ComplexityLevel.LOW and not scope_analysis.is_broad:
        return BrainDecisionResult(
            decision=BrainDecision.LOCAL_ONLY,
            confidence=0.9,
            reason="Prompt is simple, low-risk, and can proceed with local deterministic generation planning.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    strong_cases = [case for case in matched_cases if case.score >= 0.85]
    if strong_cases and not scope_analysis.is_broad and signature.complexity != ComplexityLevel.HIGH:
        return BrainDecisionResult(
            decision=BrainDecision.COMPOSE_CASES,
            confidence=0.78,
            reason="A strong local case match exists and the prompt is narrow enough to compose from memory.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    high_risk_missing = [decision for decision in scope_analysis.missing_decisions if decision.risk == RiskLevel.HIGH]
    if signature.complexity == ComplexityLevel.HIGH or scope_analysis.is_broad or high_risk_missing:
        return BrainDecisionResult(
            decision=BrainDecision.ASK_USER_BEFORE_GENERATE,
            confidence=0.82,
            reason="Prompt is broad and requires product decisions before generation.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    return BrainDecisionResult(
        decision=BrainDecision.LOCAL_PLUS_QUESTION,
        confidence=0.72,
        reason="Prompt is moderately scoped but has a few non-blocking product decisions to clarify.",
        signature=signature,
        scope_analysis=scope_analysis,
        recommended_mvp=recommended_mvp,
        matched_cases=matched_cases,
    )
