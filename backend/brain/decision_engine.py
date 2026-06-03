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
    if signature.app_type == "hello_world":
        return RecommendedMVP(
            title="Hello World App",
            features=["Static greeting", "Simple page layout"],
        )
    if signature.app_type == "crud_app":
        return RecommendedMVP(
            title="CRUD MVP",
            features=[
                "One primary entity",
                "List/create/edit/delete flow",
                "Basic form validation",
                "Local persistence",
            ],
        )
    return RecommendedMVP(
        title=f"{signature.app_type.replace('-', ' ').title()} MVP",
        features=["Core list view", "Primary detail view", "Simple local state"],
    )


def _implementation_plan(signature: PlanSignature) -> list[str]:
    if signature.app_type == "crud_app":
        return [
            "Define the primary entity and fields",
            "Build list and form screens",
            "Add create, update, and delete behavior",
            "Add the selected storage or persistence mode",
            "Validate the generated project contract",
        ]
    if signature.app_type == "inventory":
        return [
            "Confirm item schema and stock movement rules",
            "Build item list and item form",
            "Add stock adjustment behavior",
            "Add selected storage or database persistence",
            "Validate reporting and generated project contract",
        ]
    if signature.app_type == "marketplace":
        return [
            "Confirm product schema and buyer/admin scope",
            "Build product listing and detail views",
            "Add cart and simulated checkout flow",
            "Add simple admin product management",
            "Validate generated project contract",
        ]
    if signature.app_type in {"auth_app", "data_app", "dashboard"}:
        return [
            "Confirm data model and persistence boundary",
            "Confirm frontend-only versus backend/API behavior",
            "Build the smallest working UI flow",
            "Add safe local/mock persistence unless real backend is confirmed",
            "Validate generated project contract",
        ]
    return [
        "Confirm MVP scope",
        "Build core UI",
        "Add local state behavior",
        "Validate generated project contract",
    ]


def _task_list(signature: PlanSignature, scope_analysis: ScopeAnalysis) -> list[str]:
    missing_keys = [decision.key for decision in scope_analysis.missing_decisions]
    tasks = [f"Confirm {key.replace('_', ' ')}" for key in missing_keys[:5]]
    tasks.extend(["Generate implementation", "Run validation"])
    return tasks


def _result(
    *,
    decision: BrainDecision,
    confidence: float,
    reason: str,
    signature: PlanSignature,
    scope_analysis: ScopeAnalysis,
    recommended_mvp: RecommendedMVP,
    matched_cases: list[MatchedCase],
) -> BrainDecisionResult:
    planning_required = decision in {
        BrainDecision.ASK_USER_BEFORE_GENERATE,
        BrainDecision.PROVIDER_REQUIRED,
        BrainDecision.PROVIDER_REVIEW_ONLY,
    }
    return BrainDecisionResult(
        decision=decision,
        confidence=confidence,
        reason=reason,
        planning_required=planning_required,
        signature=signature,
        scope_analysis=scope_analysis,
        recommended_mvp=recommended_mvp,
        implementation_plan=_implementation_plan(signature) if planning_required else [],
        task_list=_task_list(signature, scope_analysis) if planning_required else [],
        matched_cases=matched_cases,
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
        return _result(
            decision=BrainDecision.PROVIDER_REQUIRED,
            confidence=0.72,
            reason="Prompt explicitly requires fresh external/domain knowledge that local deterministic preflight cannot verify.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    if signature.complexity == ComplexityLevel.LOW and not scope_analysis.is_broad:
        return _result(
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
        return _result(
            decision=BrainDecision.COMPOSE_CASES,
            confidence=0.78,
            reason="A strong local case match exists and the prompt is narrow enough to compose from memory.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    high_risk_missing = [decision for decision in scope_analysis.missing_decisions if decision.risk == RiskLevel.HIGH]
    crud_missing = {
        decision.key
        for decision in scope_analysis.missing_decisions
        if decision.key in {"crud_scope", "entity", "schema_fields", "storage_type", "persistence"}
    }
    if signature.app_type == "crud_app" and len(crud_missing) >= 3:
        return _result(
            decision=BrainDecision.ASK_USER_BEFORE_GENERATE,
            confidence=0.84,
            reason="CRUD prompt is ambiguous and needs entity, schema, and persistence decisions before generation.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    if signature.complexity == ComplexityLevel.HIGH or scope_analysis.is_broad or high_risk_missing:
        return _result(
            decision=BrainDecision.ASK_USER_BEFORE_GENERATE,
            confidence=0.82,
            reason="Planning required before generation because this prompt has non-trivial product or persistence decisions.",
            signature=signature,
            scope_analysis=scope_analysis,
            recommended_mvp=recommended_mvp,
            matched_cases=matched_cases,
        )

    return _result(
        decision=BrainDecision.LOCAL_PLUS_QUESTION,
        confidence=0.72,
        reason="Prompt is moderately scoped but has a few non-blocking product decisions to clarify.",
        signature=signature,
        scope_analysis=scope_analysis,
        recommended_mvp=recommended_mvp,
        matched_cases=matched_cases,
    )
