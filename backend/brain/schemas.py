from enum import Enum

from pydantic import BaseModel, Field


class BrainDecision(str, Enum):
    LOCAL_ONLY = "local_only"
    LOCAL_PLUS_QUESTION = "local_plus_question"
    ASK_USER_BEFORE_GENERATE = "ask_user_before_generate"
    PROVIDER_REQUIRED = "provider_required"
    PROVIDER_REVIEW_ONLY = "provider_review_only"
    COMPOSE_CASES = "compose_cases"


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PreflightRequest(BaseModel):
    prompt: str = Field(..., description="Raw user generation prompt")


class PlanSignature(BaseModel):
    domain: str
    intent: str
    app_type: str
    complexity: ComplexityLevel
    feature_keywords: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)


class MissingDecision(BaseModel):
    key: str
    question: str
    default_recommendation: str
    risk: RiskLevel


class ScopeAnalysis(BaseModel):
    is_broad: bool
    risk_level: RiskLevel
    missing_decisions: list[MissingDecision] = Field(default_factory=list)


class RecommendedMVP(BaseModel):
    title: str
    features: list[str] = Field(default_factory=list)


class MatchedCase(BaseModel):
    id: str
    title: str
    domain: str
    app_type: str
    score: float
    feature_keywords: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    summary: str | None = None


class BrainDecisionResult(BaseModel):
    decision: BrainDecision
    confidence: float
    reason: str
    signature: PlanSignature
    scope_analysis: ScopeAnalysis
    recommended_mvp: RecommendedMVP
    matched_cases: list[MatchedCase] = Field(default_factory=list)


class CaseMemory(BaseModel):
    id: str
    title: str
    domain: str
    app_type: str
    feature_keywords: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    summary: str | None = None


class ImplementationPlanMemory(BaseModel):
    id: str
    title: str
    domain: str
    app_type: str
    steps: list[str] = Field(default_factory=list)


class DecisionMemory(BaseModel):
    id: str
    prompt_pattern: str
    decision: BrainDecision
    reason: str


class FailureMemory(BaseModel):
    id: str
    domain: str
    app_type: str
    failure_type: str
    avoided_capabilities: list[str] = Field(default_factory=list)
    summary: str | None = None

