"""
Brain preflight routes.

This route is intentionally isolated from generation. It performs deterministic
local analysis only and never mutates workspaces or starts providers.
"""

from fastapi import APIRouter, HTTPException

from backend.brain.case_retriever import retrieve_matching_cases
from backend.brain.decision_engine import decide_preflight
from backend.brain.memory_store import ensure_memory_files
from backend.brain.plan_signature import build_plan_signature
from backend.brain.schemas import BrainDecisionResult, PreflightRequest
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
    matched_cases = retrieve_matching_cases(signature)
    return decide_preflight(prompt, signature, scope_analysis, matched_cases)

