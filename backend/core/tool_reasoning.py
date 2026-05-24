"""
ToolReasoningEngine

Reasons about WHEN to use different tools:
- grep/search
- read file
- inspect logs
- inspect runtime
- inspect artifacts
- inspect patches
- validate build

Before deciding to mutate anything.
"""

import logging
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class InvestigationTool(str, Enum):
    """Available investigation tools."""
    GREP_SEARCH = "grep_search"
    READ_FILE = "read_file"
    INSPECT_LOGS = "inspect_logs"
    INSPECT_RUNTIME = "inspect_runtime"
    INSPECT_ARTIFACTS = "inspect_artifacts"
    INSPECT_PATCHES = "inspect_patches"
    VALIDATE_BUILD = "validate_build"
    SEMANTIC_SEARCH = "semantic_search"
    TRACE_DEPENDENCY = "trace_dependency"


class MutationType(str, Enum):
    """Types of code mutations."""
    INSERT_IMPORT = "insert_import"
    INJECT_COMPONENT = "inject_component"
    APPEND_BLOCK = "append_block"
    MODIFY_EXISTING = "modify_existing"
    REPLACE_FILE = "replace_file"
    CREATE_NEW_FILE = "create_new_file"


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class InvestigationAction:
    """A single investigation action."""
    tool: InvestigationTool
    target: str  # symbol, file, pattern, etc.
    reason: str  # why we need this info
    confidence_gain: float  # expected confidence increase (0.0-1.0)
    
    def __str__(self):
        return f"{self.tool.value} on '{self.target}': {self.reason}"


@dataclass
class ToolReasoningAnalysis:
    """Result of tool reasoning."""
    mutation_type: MutationType
    risk_level: RiskLevel
    target_file: str
    affected_symbols: List[str]
    required_investigations: List[InvestigationAction]
    mutation_risks: List[str]
    estimated_scope: str  # 'minimal', 'moderate', 'broad'
    confidence: float  # 0.0-1.0
    reasoning: str  # explanation of the plan


class ToolReasoningEngine:
    """
    Reasons about what investigations to perform before mutations.
    
    Core principle:
    - Before mutating anything, the system must ask:
      1. What do I need to understand?
      2. How can I discover it with minimal cost?
      3. What are the mutation risks?
      4. What are the smallest possible mutations?
    """

    def __init__(self, repo_map: Optional[Any] = None, semantic_engine: Optional[Any] = None):
        self.repo_map = repo_map
        self.semantic_engine = semantic_engine
        self.investigation_history: Dict[str, List[InvestigationAction]] = {}

    def analyze_mutation_request(
        self,
        prompt: str,
        context_files: List[str],
        target_mutation: MutationType,
    ) -> ToolReasoningAnalysis:
        """
        Analyze a mutation request and determine what needs investigation.
        
        Args:
            prompt: User request (e.g., "Add a new login component")
            context_files: Files already provided
            target_mutation: Type of mutation planned
        
        Returns:
            ToolReasoningAnalysis with investigation plan
        """
        logger.info(f"Reasoning about mutation: {target_mutation}")
        
        investigations = []
        risks = []
        affected_symbols = []
        confidence = 0.0
        
        # ========== Analyze mutation type ==========
        
        if target_mutation == MutationType.INSERT_IMPORT:
            # Risk: Low - just adding an import
            investigations.extend(self._investigate_import_mutation(context_files))
            risks.extend([
                "Circular import may occur",
                "Module may not exist at that path",
            ])
            confidence = 0.85
        
        elif target_mutation == MutationType.INJECT_COMPONENT:
            # Risk: Medium - adding component to existing structure
            investigations.extend(self._investigate_component_injection(context_files, prompt))
            risks.extend([
                "Component may not match expected interface",
                "Parent component may not accept this child",
                "Styling may conflict",
            ])
            confidence = 0.70
        
        elif target_mutation == MutationType.APPEND_BLOCK:
            # Risk: Medium - adding code block
            investigations.extend(self._investigate_block_append(context_files))
            risks.extend([
                "Code may have syntax errors",
                "May reference undefined variables",
                "May conflict with existing logic",
            ])
            confidence = 0.75
        
        elif target_mutation == MutationType.MODIFY_EXISTING:
            # Risk: High - changing existing code
            investigations.extend(self._investigate_modification(context_files))
            risks.extend([
                "May break existing functionality",
                "May affect other dependent code",
                "May introduce subtle bugs",
            ])
            confidence = 0.60
        
        elif target_mutation == MutationType.REPLACE_FILE:
            # Risk: Critical - full file replacement
            investigations.extend(self._investigate_replacement(context_files))
            risks.extend([
                "Loss of custom modifications",
                "May break imports/exports",
                "May remove critical infrastructure code",
            ])
            confidence = 0.40
        
        elif target_mutation == MutationType.CREATE_NEW_FILE:
            # Risk: Medium - new file
            investigations.extend(self._investigate_new_file(context_files, prompt))
            risks.extend([
                "May not integrate with build system",
                "Import paths may be incorrect",
                "May be placed in wrong directory",
            ])
            confidence = 0.70
        
        # ========== Determine risk level ==========
        
        risk_level = self._calculate_risk_level(
            target_mutation, len(context_files), len(risks)
        )
        
        # ========== Estimate scope ==========
        
        estimated_scope = self._estimate_mutation_scope(
            target_mutation, context_files, affected_symbols
        )
        
        # ========== Build reasoning ==========
        
        reasoning = self._build_reasoning(
            prompt, target_mutation, risk_level, investigations
        )
        
        target_file = context_files[0] if context_files else "unknown"
        
        return ToolReasoningAnalysis(
            mutation_type=target_mutation,
            risk_level=risk_level,
            target_file=target_file,
            affected_symbols=affected_symbols,
            required_investigations=investigations,
            mutation_risks=risks,
            estimated_scope=estimated_scope,
            confidence=confidence,
            reasoning=reasoning,
        )

    def evaluate_investigation_completeness(
        self,
        analysis: ToolReasoningAnalysis,
        completed_investigations: Dict[str, Any],
    ) -> float:
        """
        Evaluate how well completed investigations cover the analysis.
        
        Returns:
            Confidence increase (0.0-1.0)
        """
        coverage = 0.0
        required = len(analysis.required_investigations)
        
        if required == 0:
            return 1.0
        
        for action in analysis.required_investigations:
            if action.target in completed_investigations:
                coverage += 1.0
        
        return min(1.0, coverage / required)

    def recommend_safe_mutations(
        self,
        target_mutation: MutationType,
        num_options: int = 3,
    ) -> List[str]:
        """
        Recommend safest mutation strategies for the target type.
        """
        recommendations = {
            MutationType.INSERT_IMPORT: [
                "Insert at top of file after existing imports",
                "Use named imports where available",
                "Check for existing re-exports of the same module",
            ],
            MutationType.INJECT_COMPONENT: [
                "Inject as last child of parent component",
                "Pass minimal required props",
                "Ensure parent can accept children",
                "Verify no naming conflicts",
            ],
            MutationType.APPEND_BLOCK: [
                "Append to end of file/section",
                "Add after blank line separator",
                "Verify no syntax conflicts",
                "Test in isolation first",
            ],
            MutationType.MODIFY_EXISTING: [
                "Use minimal targeted replacements",
                "Preserve surrounding context",
                "Document the change",
                "Test all affected code paths",
            ],
            MutationType.CREATE_NEW_FILE: [
                "Create in standard location (src/components, src/pages, etc)",
                "Follow existing naming conventions",
                "Create with minimal boilerplate",
                "Generate export statement matching project patterns",
            ],
            MutationType.REPLACE_FILE: [
                "Avoid if possible - prefer append/inject",
                "If necessary, preserve existing exports",
                "Maintain import/export interface",
                "Extensive testing required",
            ],
        }
        
        opts = recommendations.get(target_mutation, [])
        return opts[:num_options]

    # ========== PRIVATE HELPERS ==========

    def _investigate_import_mutation(self, context_files: List[str]) -> List[InvestigationAction]:
        """Investigations for import insertion."""
        return [
            InvestigationAction(
                tool=InvestigationTool.SEMANTIC_SEARCH,
                target="import sources",
                reason="Find where symbols are exported from",
                confidence_gain=0.3,
            ),
            InvestigationAction(
                tool=InvestigationTool.GREP_SEARCH,
                target="existing imports in target file",
                reason="Check import style and location patterns",
                confidence_gain=0.2,
            ),
        ]

    def _investigate_component_injection(
        self, context_files: List[str], prompt: str
    ) -> List[InvestigationAction]:
        """Investigations for component injection."""
        actions = [
            InvestigationAction(
                tool=InvestigationTool.SEMANTIC_SEARCH,
                target="parent component props interface",
                reason="Ensure injected component matches expected interface",
                confidence_gain=0.4,
            ),
            InvestigationAction(
                tool=InvestigationTool.READ_FILE,
                target="parent component structure",
                reason="Understand where children are rendered",
                confidence_gain=0.3,
            ),
        ]
        
        # Check if we're injecting into an existing component
        if context_files:
            actions.append(InvestigationAction(
                tool=InvestigationTool.TRACE_DEPENDENCY,
                target=context_files[0],
                reason="Map component dependency tree",
                confidence_gain=0.25,
            ))
        
        return actions

    def _investigate_block_append(self, context_files: List[str]) -> List[InvestigationAction]:
        """Investigations for code block append."""
        return [
            InvestigationAction(
                tool=InvestigationTool.READ_FILE,
                target="end of target file",
                reason="Understand current file structure and syntax",
                confidence_gain=0.4,
            ),
            InvestigationAction(
                tool=InvestigationTool.GREP_SEARCH,
                target="variable/function names used in block",
                reason="Detect undefined references",
                confidence_gain=0.35,
            ),
        ]

    def _investigate_modification(self, context_files: List[str]) -> List[InvestigationAction]:
        """Investigations for code modification."""
        return [
            InvestigationAction(
                tool=InvestigationTool.READ_FILE,
                target="full context of modified section",
                reason="Understand exact code being changed",
                confidence_gain=0.5,
            ),
            InvestigationAction(
                tool=InvestigationTool.SEMANTIC_SEARCH,
                target="usages of modified symbol",
                reason="Find all code that depends on this",
                confidence_gain=0.4,
            ),
            InvestigationAction(
                tool=InvestigationTool.INSPECT_LOGS,
                target="test results",
                reason="Identify currently passing tests",
                confidence_gain=0.3,
            ),
        ]

    def _investigate_replacement(self, context_files: List[str]) -> List[InvestigationAction]:
        """Investigations for file replacement."""
        return [
            InvestigationAction(
                tool=InvestigationTool.READ_FILE,
                target="current file exports and interface",
                reason="Ensure replacement maintains API compatibility",
                confidence_gain=0.5,
            ),
            InvestigationAction(
                tool=InvestigationTool.SEMANTIC_SEARCH,
                target="all imports of this file",
                reason="Map all dependent code",
                confidence_gain=0.45,
            ),
            InvestigationAction(
                tool=InvestigationTool.INSPECT_LOGS,
                target="test coverage of this file",
                reason="Identify critical functionality",
                confidence_gain=0.4,
            ),
        ]

    def _investigate_new_file(
        self, context_files: List[str], prompt: str
    ) -> List[InvestigationAction]:
        """Investigations for new file creation."""
        return [
            InvestigationAction(
                tool=InvestigationTool.SEMANTIC_SEARCH,
                target="similar existing files",
                reason="Find patterns for structure and naming",
                confidence_gain=0.4,
            ),
            InvestigationAction(
                tool=InvestigationTool.GREP_SEARCH,
                target="directory structure patterns",
                reason="Determine correct placement",
                confidence_gain=0.3,
            ),
        ]

    def _calculate_risk_level(
        self,
        mutation_type: MutationType,
        num_context_files: int,
        num_risks: int,
    ) -> RiskLevel:
        """Calculate risk level based on mutation characteristics."""
        base_risks = {
            MutationType.INSERT_IMPORT: 0,
            MutationType.INJECT_COMPONENT: 1,
            MutationType.APPEND_BLOCK: 1,
            MutationType.MODIFY_EXISTING: 2,
            MutationType.CREATE_NEW_FILE: 1,
            MutationType.REPLACE_FILE: 3,
        }
        
        # Base risk is the primary factor
        base_risk = base_risks.get(mutation_type, 2)
        
        # Add a small amount for additional risks (but cap it)
        additional_risk = min(1, num_risks * 0.1)
        risk_score = base_risk + additional_risk
        
        if risk_score >= 3.0:
            return RiskLevel.CRITICAL
        elif risk_score >= 2.0:
            return RiskLevel.HIGH
        elif risk_score >= 1.0:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _estimate_mutation_scope(
        self,
        mutation_type: MutationType,
        context_files: List[str],
        affected_symbols: List[str],
    ) -> str:
        """Estimate the scope of the mutation."""
        scopes = {
            MutationType.INSERT_IMPORT: "minimal",
            MutationType.INJECT_COMPONENT: "moderate",
            MutationType.APPEND_BLOCK: "moderate",
            MutationType.MODIFY_EXISTING: "moderate",
            MutationType.CREATE_NEW_FILE: "minimal",
            MutationType.REPLACE_FILE: "broad",
        }
        return scopes.get(mutation_type, "moderate")

    def assess_structural_mutation_risks(
        self,
        target_files: List[str],
    ) -> Dict[str, Any]:
        """
        Assess structural risks of mutations:
        - ripple depth
        - ownership complexity
        - dependency locality
        - collision risk
        """
        if not self.repo_map or not hasattr(self.repo_map, 'dependency_ripples'):
            return {
                'ripple_depth': 0,
                'ownership_complexity': 'unknown',
                'dependency_locality': 3,  # neutral
                'collision_risk': 2,  # medium
                'circular_deps': [],
            }
        
        ripple_depths = []
        circular_deps = []
        ownership_zones = set()
        collision_risks = []
        
        for target in target_files:
            ripple = self.repo_map.dependency_ripples.get(target)
            if not ripple:
                continue
            
            ripple_depths.append(ripple.ripple_depth)
            if ripple.circular_deps:
                circular_deps.extend(ripple.circular_deps)
            
            # Extract ownership zone
            parts = target.split('/')
            if len(parts) > 1:
                ownership_zones.add(parts[0])
            
            # Collision risk
            if ripple.is_critical:
                collision_risks.append(4)
            else:
                collision_risks.append(2 + ripple.ripple_depth // 2)
        
        # Determine complexity
        if len(ownership_zones) > 2:
            complexity = 'high'
        elif len(ownership_zones) > 1:
            complexity = 'moderate'
        else:
            complexity = 'low'
        
        return {
            'ripple_depth': max(ripple_depths) if ripple_depths else 0,
            'ownership_complexity': complexity,
            'dependency_locality': max(collision_risks) if collision_risks else 3,
            'collision_risk': max(collision_risks) if collision_risks else 2,
            'circular_deps': list(set(circular_deps)),
            'affected_ownership_zones': list(ownership_zones),
        }

    def score_dependency_locality(
        self,
        target_file: str,
    ) -> int:
        """
        Score dependency locality: 1=isolated, 5=high ripple.
        
        Based on ripple analysis from repo_map.
        """
        if not self.repo_map or not hasattr(self.repo_map, 'dependency_ripples'):
            # Heuristic: core files are higher locality
            if any(part in target_file for part in ['core', 'shared', 'utils']):
                return 4
            if any(part in target_file for part in ['components', 'features']):
                return 2
            return 3  # neutral
        
        ripple = self.repo_map.dependency_ripples.get(target_file)
        if not ripple:
            return 3
        
        # Map ripple depth to locality score
        # Depth 0 = isolated (1), Depth 3+ = high ripple (5)
        locality = min(5, max(1, ripple.ripple_depth + 1))
        
        # Adjust for critical files
        if ripple.is_critical:
            locality = min(5, locality + 1)
        
        return locality

    def _build_reasoning(
        self,
        prompt: str,
        mutation_type: MutationType,
        risk_level: RiskLevel,
        investigations: List[InvestigationAction],
    ) -> str:
        """Build human-readable reasoning."""
        lines = [
            f"Request: {prompt[:100]}...",
            f"Mutation Type: {mutation_type.value}",
            f"Risk Level: {risk_level.value.upper()}",
            f"Required Investigations ({len(investigations)}):",
        ]
        for inv in investigations[:3]:  # Show first 3
            lines.append(f"  - {inv}")
        if len(investigations) > 3:
            lines.append(f"  - ... and {len(investigations) - 3} more")
        
        return "\n".join(lines)


def create_tool_reasoning_engine(
    repo_map: Optional[Any] = None,
    semantic_engine: Optional[Any] = None,
) -> ToolReasoningEngine:
    """Create a tool reasoning engine."""
    return ToolReasoningEngine(repo_map, semantic_engine)
