from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .actions import ActionPlan
    from .capabilities import ContractCapability


@dataclass
class FeatureDescriptor:
    id: str
    category: str = "unknown"
    confidence: float = 0.0
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureManifest:
    project_id: str
    run_id: str
    app_type: str | None = None
    domain: str | None = None
    features: list[FeatureDescriptor] = field(default_factory=list)
    source: str = "feature_extraction"

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "run_id": self.run_id,
            "app_type": self.app_type,
            "domain": self.domain,
            "source": self.source,
            "features": [feature.to_dict() for feature in self.features],
        }


@dataclass(frozen=True)
class ContractDescriptor:
    contract_id: str
    capability: "ContractCapability"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "capability": self.capability.value,
            "description": self.description,
        }


@dataclass
class FeatureContractContext:
    project_id: str
    run_id: str
    preview_url: str
    prompt: str
    app_type: str | None = None
    domain: str | None = None
    generation_signature: Any | None = None
    feature_manifest: FeatureManifest | None = None


@dataclass
class FeatureContractFailure:
    contract_id: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureContractResult:
    success: bool
    contracts_executed: list[str] = field(default_factory=list)
    selected_contracts: list[str] = field(default_factory=list)
    action_plans: list["ActionPlan"] = field(default_factory=list)
    failures: list[FeatureContractFailure] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "contracts_executed": self.contracts_executed,
            "selected_contracts": self.selected_contracts,
            "action_plans": [plan.to_dict() for plan in self.action_plans],
            "failures": [failure.to_dict() for failure in self.failures],
            "duration_ms": self.duration_ms,
        }
