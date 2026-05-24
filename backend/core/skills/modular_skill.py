from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from backend.core.skills.interfaces import BaseSkill, SkillMetadata, CommandStrategy, PreviewStrategy

@dataclass
class ExecutionConstraints:
    requires_build: bool = True
    requires_dependencies: bool = True
    isolated_cwd: bool = True
    allowed_file_patterns: list[str] = field(default_factory=lambda: ["*"])

@dataclass
class VerificationStrategy:
    verify_html: bool = True
    verify_source_marker: bool = False
    verify_dom: bool = True
    success_criteria: list[str] = field(default_factory=list)
    timeout_ms: int = 15000

class ModularSkill(BaseSkill):
    """
    ModularSkill represents the ecosystem-agnostic capability contract.
    It extends BaseSkill to explicitly declare runtime boundaries, verification constraints,
    and planning parameters, allowing the Orchestrator to treat it as a pluggable capability.
    """
    
    @abstractmethod
    def get_execution_constraints(self) -> ExecutionConstraints:
        """Define boundaries for sandbox execution."""
        return ExecutionConstraints()

    @abstractmethod
    def get_verification_strategy(self) -> VerificationStrategy:
        """Define how tasks and previews should be verified for this ecosystem."""
        return VerificationStrategy()

    @abstractmethod
    def get_planning_capabilities(self) -> list[str]:
        """Return higher-order AI planning capabilities this skill supports."""
        return []
