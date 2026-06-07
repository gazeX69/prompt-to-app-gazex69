"""
Brain preflight routes.

This route is intentionally isolated from generation. It performs deterministic
local analysis only and never mutates workspaces or starts providers.
"""

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder

from backend.brain.case_retriever import retrieve_matching_cases
from backend.brain.decision_engine import decide_preflight
from backend.brain.memory_store import append_decision_history, ensure_memory_files
from backend.brain.plan_signature import build_plan_signature
from backend.brain.schemas import (
    BrainDecision,
    BrainDecisionResult,
    ComplexityLevel,
    DecisionOption,
    DiscoveryAnswerRequest,
    DiscoveryStartRequest,
    MissingDecision,
    PreflightHistoryRequest,
    PreflightHistoryResponse,
    PreflightRequest,
    DevelopmentAdvisory,
    RiskLevel,
)
from backend.brain.scope_analyzer import analyze_scope

router = APIRouter()


@router.post("/preflight", response_model=BrainDecisionResult)
def preflight(req: PreflightRequest) -> BrainDecisionResult:
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")

    ensure_memory_files()
    signature = build_plan_signature(prompt)
    scope_analysis = analyze_scope(prompt, signature)
    matched_cases = retrieve_matching_cases(signature, prompt=prompt)

    
    result = decide_preflight(prompt, signature, scope_analysis, matched_cases)
    try:
        from backend.brain.discovery_tree.discovery_engine import restore_discovery, should_start_discovery, start_discovery

        discovery_turn = None
        if req.discovery_session_id:
            discovery_turn = restore_discovery(req.discovery_session_id, req.project_id)
        elif should_start_discovery(prompt):
            discovery_turn = start_discovery(prompt, req.project_id)

        if discovery_turn and not discovery_turn.complete and discovery_turn.question:
            result.decision = BrainDecision.ASK_USER_BEFORE_GENERATE
            result.planning_required = True
            result.reason = "Discovery session requires a structured answer before generation."
            result.discovery_session = jsonable_encoder(discovery_turn)
            result.scope_analysis.is_broad = True
            result.scope_analysis.risk_level = RiskLevel.MEDIUM
            result.scope_analysis.missing_decisions = [
                MissingDecision(
                    key=f"discovery_{discovery_turn.field or 'answer'}",
                    question=discovery_turn.question,
                    default_recommendation="Answer this discovery question before generation",
                    risk=RiskLevel.MEDIUM,
                    options=[],
                )
            ]
            return result
        if discovery_turn and discovery_turn.complete:
            result.discovery_session = jsonable_encoder(discovery_turn)
            result.project_state = discovery_turn.draft_state
    except Exception:
        result.discovery_session = None
    try:
        from backend.brain.dss_engine import get_dss_recommendations

        result.dss_recommendations = get_dss_recommendations(scope_analysis.missing_decisions)
    except Exception:
        result.dss_recommendations = []

    if req.project_id:
        try:
            from backend.memory.project_memory import ProjectMemory
            from backend.brain.change_scope import ChangeScopeAnalyzer

            ProjectMemory.initialize_project(req.project_id, "unknown")
            result.project_state = ProjectMemory.load_for(req.project_id, "preflight")
            result.project_action = ProjectMemory.classify_action(req.project_id, prompt)
            try:
                from backend.memory.workspace_awareness import WorkspaceAwareness

                awareness = WorkspaceAwareness.scan(req.project_id, prompt=prompt)
                result.workspace_awareness = awareness
                result.workspace_impact = awareness.get("impact_analysis")
            except Exception:
                result.workspace_awareness = None
                result.workspace_impact = None
            result.change_scope = ChangeScopeAnalyzer.analyze(
                req.project_id,
                prompt,
                project_state=result.project_state,
                project_action=result.project_action,
                workspace_awareness=result.workspace_awareness,
            )
            if (
                result.project_action
                and result.project_action.get("action") == "modify"
                and result.project_state
                and result.project_action.get("has_existing_project")
            ):
                existing_type = result.project_state.get("project_type") or result.signature.app_type
                existing_features = result.project_state.get("features") or []
                change_scope = result.change_scope or {}
                is_small_scope = change_scope.get("scope_size") == "small" and change_scope.get("safe_to_patch_locally")
                if is_small_scope:
                    result.decision = BrainDecision.LOCAL_ONLY
                    result.planning_required = False
                else:
                    result.decision = BrainDecision.LOCAL_PLUS_QUESTION
                    result.planning_required = True
                result.confidence = max(
                    float(result.project_action.get("confidence") or 0.0),
                    float(change_scope.get("confidence") or 0.0),
                    0.72,
                )
                result.reason = (
                    "Project State plus Change Scope Analysis is the current source of truth: this prompt is "
                    f"interpreted as a {change_scope.get('scope_size', 'scoped')} MODIFY request against the "
                    f"existing {existing_type} project, with confidence-based impact estimation."
                )
                result.signature.domain = existing_type if existing_type != "unknown" else result.signature.domain
                result.signature.app_type = existing_type if existing_type != "unknown" else result.signature.app_type
                if change_scope.get("scope_size") == "large":
                    result.signature.complexity = ComplexityLevel.HIGH
                elif change_scope.get("scope_size") in {"medium", "unclear"}:
                    result.signature.complexity = ComplexityLevel.MEDIUM
                else:
                    result.signature.complexity = ComplexityLevel.LOW
                result.signature.feature_keywords = list(existing_features)
                change_type = change_scope.get("change_type") or "targeted_project_modification"
                result.signature.required_capabilities = [change_type]
                result.recommended_mvp.title = f"{str(existing_type).replace('_', ' ').title()} Modification"
                if "style_update" in result.signature.required_capabilities:
                    result.recommended_mvp.features = ["Targeted styling update", "Preserve existing UI", "Validate preview"]
                elif "content_addition" in result.signature.required_capabilities:
                    result.recommended_mvp.features = ["Add requested content", "Preserve existing styling", "Validate preview"]
                else:
                    result.recommended_mvp.features = ["Targeted project modification", "Preserve existing features", "Validate result"]
                result.scope_analysis.is_broad = change_scope.get("scope_size") in {"medium", "large", "unclear"}
                if change_scope.get("scope_size") == "large":
                    result.scope_analysis.risk_level = RiskLevel.HIGH
                elif change_scope.get("scope_size") in {"medium", "unclear"}:
                    result.scope_analysis.risk_level = RiskLevel.MEDIUM
                else:
                    result.scope_analysis.risk_level = RiskLevel.LOW
                result.scope_analysis.missing_decisions = [
                    MissingDecision(
                        key=f"change_scope_{index + 1}",
                        question=question,
                        default_recommendation="Narrow the change before generation",
                        risk=result.scope_analysis.risk_level,
                        options=[
                            DecisionOption(text="Keep change minimal", score=0.84, is_recommended=True),
                            DecisionOption(text="Expand scope intentionally", score=0.46, is_recommended=False),
                        ],
                    )
                    for index, question in enumerate(change_scope.get("clarifying_questions") or [])
                ]
                result.implementation_plan = [
                    "Load Project State and active workspace context",
                    "Run Change Scope Analysis and identify the smallest affected file(s)",
                    "Apply the requested modification without recreating the app",
                    "Run validation and update Project State",
                ]
                result.task_list = [
                    "Confirm existing project identity",
                    f"Classify scope as {change_scope.get('scope_size', 'unknown')}",
                    "Patch only target files: " + (", ".join(change_scope.get("target_files") or []) or "identify before patch"),
                    "Run validation: " + (", ".join(change_scope.get("required_validation") or []) or "source_check"),
                ]
        except Exception:
            result.project_state = None
            result.project_action = None
            result.change_scope = None
    
    # Calculate domain decomposition and vertical slices
    try:
        from backend.planner.domain_analyzer import analyze_domain
        from backend.planner.slice_planner import plan_vertical_slices
        
        # Only run DDD planning for broad/complex requests
        if result.scope_analysis.is_broad or result.signature.complexity == "high":
            subdomains = analyze_domain(prompt)
            slices = plan_vertical_slices(subdomains)
            
            result.subdomains = subdomains
            result.vertical_slices = slices
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Failed to calculate DDD domain and slices plan: %s", e)
        
    return result


@router.post("/discovery/start")
def start_discovery_session(req: DiscoveryStartRequest) -> dict:
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt must not be empty.")
    try:
        from backend.brain.discovery_tree.discovery_engine import start_discovery

        return jsonable_encoder(start_discovery(prompt, req.project_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/discovery/answer")
def answer_discovery_session(req: DiscoveryAnswerRequest) -> dict:
    answer = req.answer.strip()
    if not answer:
        raise HTTPException(status_code=400, detail="Answer must not be empty.")
    try:
        from backend.brain.discovery_tree.discovery_engine import answer_discovery

        return jsonable_encoder(answer_discovery(req.session_id, answer, req.project_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/discovery/session/{session_id}")
def get_discovery_session(session_id: str, project_id: str | None = None) -> dict:
    try:
        from backend.brain.discovery_tree.discovery_engine import restore_discovery

        return jsonable_encoder(restore_discovery(session_id, project_id))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/preflight/history", response_model=PreflightHistoryResponse)
def append_preflight_history(
    req: PreflightHistoryRequest,
) -> PreflightHistoryResponse:
    record = append_decision_history(jsonable_encoder(req))
    return PreflightHistoryResponse(ok=True, record=record)


@router.get("/advisory/{project_id}/{run_id}", response_model=DevelopmentAdvisory)
def get_development_advisory(project_id: str, run_id: str) -> DevelopmentAdvisory:
    from backend.core.scanner.run_manifest import read_run_manifest
    from backend.brain.developer_advisor import DeveloperAdvisor
    
    manifest = read_run_manifest(project_id, run_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Project run manifest not found.")
        
    prompt = manifest.get("prompt") or "Default application generation"
    status = manifest.get("status") or "succeeded"
    is_success = (status == "succeeded")
    
    advisory = DeveloperAdvisor.generate_suggestions(project_id, run_id, prompt, is_success)
    return advisory
