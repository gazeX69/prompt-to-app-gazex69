"""
InvestigationPlanGenerator

Generates detailed investigation plans before patch generation.

InvestigationPlan:
* files to inspect
* symbols to trace
* commands to run
* validations required
* mutation risks
"""

import logging
from typing import List, Dict, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class FileInspection:
    """Specification for inspecting a file."""
    file_path: str
    reason: str  # why we need to inspect this
    look_for: List[str]  # specific patterns/symbols to find
    section: Optional[str] = None  # specific section (imports, exports, etc.)
    priority: int = 0  # 0=critical, 1=important, 2=optional


@dataclass
class SymbolTrace:
    """Specification for tracing a symbol."""
    symbol_name: str
    symbol_type: str  # 'function', 'class', 'component', etc.
    find_usages: bool = True
    find_definition: bool = True
    max_depth: int = 3  # how many levels to trace


@dataclass
class CommandToRun:
    """Specification for running a command."""
    command: str
    reason: str
    expected_output: Optional[str] = None
    fail_ok: bool = False  # if failure is expected/acceptable


@dataclass
class ValidationScenario:
    """Specification for validation."""
    name: str
    validation_command: str
    success_condition: str
    failure_impact: str
    is_blocking: bool = False  # if failure blocks mutation


@dataclass
class MutationRisk:
    """Identified risk from investigation."""
    risk_id: str
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    affected_areas: List[str]
    mitigation: str


@dataclass
class InvestigationPlan:
    """Complete investigation plan before patching."""
    request_summary: str
    mutation_type: str
    target_files: List[str]
    
    # Investigation phases
    file_inspections: List[FileInspection]
    symbol_traces: List[SymbolTrace]
    commands_to_run: List[CommandToRun]
    validations_required: List[ValidationScenario]
    identified_risks: List[MutationRisk]
    
    # Metadata
    estimated_investigation_time: float  # seconds
    confidence_after_investigation: float  # 0.0-1.0
    safe_to_proceed: bool = False
    
    def num_critical_files(self) -> int:
        """Count critical file inspections."""
        return sum(1 for f in self.file_inspections if f.priority == 0)
    
    def num_high_severity_risks(self) -> int:
        """Count high/critical severity risks."""
        return sum(1 for r in self.identified_risks if r.severity in ['high', 'critical'])


class InvestigationPlanGenerator:
    """
    Generates detailed investigation plans.
    
    Before mutation, the AI must know:
    1. What files to inspect
    2. What symbols to trace
    3. What commands to validate
    4. What validations must pass
    5. What risks exist
    """

    def __init__(
        self,
        repo_map: Optional[Any] = None,
        semantic_engine: Optional[Any] = None,
        tool_reasoning: Optional[Any] = None,
    ):
        self.repo_map = repo_map
        self.semantic_engine = semantic_engine
        self.tool_reasoning = tool_reasoning

    def generate_plan(
        self,
        request: str,
        mutation_type: str,
        target_files: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> InvestigationPlan:
        """
        Generate a complete investigation plan.
        
        Args:
            request: User request/prompt
            mutation_type: Type of mutation (insert_import, inject_component, etc.)
            target_files: Files that will be modified
            context: Optional additional context
        
        Returns:
            InvestigationPlan with all details
        """
        logger.info(f"Generating investigation plan for: {request[:80]}")
        
        file_inspections = self._generate_file_inspections(mutation_type, target_files)
        symbol_traces = self._generate_symbol_traces(target_files)
        commands = self._generate_validation_commands(mutation_type)
        validations = self._generate_validation_scenarios(mutation_type, target_files)
        risks = self._identify_mutation_risks(mutation_type, target_files)
        
        # Estimate time based on number of inspections
        est_time = (
            len(file_inspections) * 0.5 +
            len(symbol_traces) * 1.0 +
            len(commands) * 2.0
        )
        
        # Calculate confidence
        confidence = self._calculate_investigation_confidence(
            len(file_inspections),
            len(symbol_traces),
            len(risks),
        )
        
        # Determine if safe to proceed
        high_risks = sum(1 for r in risks if r.severity == 'critical')
        safe_to_proceed = high_risks == 0 and confidence >= 0.65
        
        return InvestigationPlan(
            request_summary=request,
            mutation_type=mutation_type,
            target_files=target_files,
            file_inspections=file_inspections,
            symbol_traces=symbol_traces,
            commands_to_run=commands,
            validations_required=validations,
            identified_risks=risks,
            estimated_investigation_time=est_time,
            confidence_after_investigation=confidence,
            safe_to_proceed=safe_to_proceed,
        )

    def generate_for_react_component_addition(
        self,
        component_name: str,
        parent_component: str,
        target_files: List[str],
    ) -> InvestigationPlan:
        """
        Specialized plan for adding a React component.
        """
        return self.generate_plan(
            request=f"Add {component_name} to {parent_component}",
            mutation_type="inject_component",
            target_files=target_files,
            context={
                "component_name": component_name,
                "parent_component": parent_component,
            }
        )

    def generate_for_new_api_endpoint(
        self,
        endpoint_path: str,
        method: str,
        handler_file: str,
    ) -> InvestigationPlan:
        """
        Specialized plan for adding API endpoint.
        """
        return self.generate_plan(
            request=f"Add {method} {endpoint_path} endpoint",
            mutation_type="append_block",
            target_files=[handler_file],
            context={
                "endpoint": endpoint_path,
                "method": method,
            }
        )

    # ========== PRIVATE HELPERS ==========

    def _generate_file_inspections(
        self,
        mutation_type: str,
        target_files: List[str],
    ) -> List[FileInspection]:
        """Generate file inspection specifications."""
        inspections = []
        
        # Always inspect target files
        for file_path in target_files:
            inspections.append(FileInspection(
                file_path=file_path,
                reason="Primary target file for mutation",
                look_for=["imports", "exports", "function definitions"],
                priority=0,
            ))
        
        # Mutation-specific inspections
        if mutation_type == "inject_component":
            # Look for parent component structure
            inspections.append(FileInspection(
                file_path=target_files[0] if target_files else "",
                reason="Understand parent component JSX structure",
                look_for=["return statements", "render calls", "child components"],
                section="JSX",
                priority=0,
            ))
            
            # Check for existing imports
            inspections.append(FileInspection(
                file_path=target_files[0] if target_files else "",
                reason="Identify import patterns and style",
                look_for=["import statements"],
                section="imports",
                priority=1,
            ))
        
        elif mutation_type == "insert_import":
            # Check existing imports
            inspections.append(FileInspection(
                file_path=target_files[0] if target_files else "",
                reason="Find where to insert new import",
                look_for=["import statements"],
                section="imports",
                priority=0,
            ))
        
        elif mutation_type == "append_block":
            # Check end of file
            inspections.append(FileInspection(
                file_path=target_files[0] if target_files else "",
                reason="Understand file structure and syntax context",
                look_for=["last function", "exports"],
                section="end",
                priority=0,
            ))
            
            # Check for dependencies
            inspections.append(FileInspection(
                file_path=target_files[0] if target_files else "",
                reason="Identify available functions/variables",
                look_for=["function definitions", "imports"],
                section="available symbols",
                priority=1,
            ))
        
        elif mutation_type == "create_new_file":
            # Check similar files for patterns
            inspections.append(FileInspection(
                file_path="src/components/Example.tsx",  # placeholder
                reason="Learn component file structure patterns",
                look_for=["imports", "export statement", "function signature"],
                priority=1,
            ))
        
        return inspections

    def _generate_symbol_traces(
        self,
        target_files: List[str],
    ) -> List[SymbolTrace]:
        """Generate symbol trace specifications."""
        traces = []
        
        # For each target file, trace its exports
        for file_path in target_files:
            traces.append(SymbolTrace(
                symbol_name=f"exports of {file_path}",
                symbol_type="module exports",
                find_usages=True,
                find_definition=False,
                max_depth=2,
            ))
        
        return traces

    def _generate_validation_commands(
        self,
        mutation_type: str,
    ) -> List[CommandToRun]:
        """Generate commands to validate preconditions."""
        commands = []
        
        # Type-specific validations
        if mutation_type == "inject_component":
            commands.append(CommandToRun(
                command="npm run type-check",
                reason="Ensure TypeScript types are valid",
                expected_output="no type errors",
                fail_ok=False,
            ))
        
        elif mutation_type == "append_block":
            commands.append(CommandToRun(
                command="npm run lint",
                reason="Check for syntax issues",
                expected_output="0 warnings",
                fail_ok=False,
            ))
        
        # Always validate build compatibility
        commands.append(CommandToRun(
            command="npm run build 2>&1 | head -20",
            reason="Ensure no obvious build issues",
            fail_ok=True,  # Current build may fail, we just want baseline
        ))
        
        return commands

    def _generate_validation_scenarios(
        self,
        mutation_type: str,
        target_files: List[str],
    ) -> List[ValidationScenario]:
        """Generate validation scenarios that must pass."""
        validations = []
        
        # Always need syntax validation
        validations.append(ValidationScenario(
            name="Syntax Check",
            validation_command="npm run lint -- --fix",
            success_condition="No linting errors",
            failure_impact="Code will not run",
            is_blocking=True,
        ))
        
        # Build validation
        validations.append(ValidationScenario(
            name="Build Validation",
            validation_command="npm run build",
            success_condition="Build succeeds",
            failure_impact="App cannot be deployed",
            is_blocking=True,
        ))
        
        # Type validation for TypeScript
        if any(f.endswith('.tsx') or f.endswith('.ts') for f in target_files):
            validations.append(ValidationScenario(
                name="Type Checking",
                validation_command="npm run type-check",
                success_condition="No type errors",
                failure_impact="Runtime type errors possible",
                is_blocking=True,
            ))
        
        # Import validation
        if "insert_import" in mutation_type:
            validations.append(ValidationScenario(
                name="Import Resolution",
                validation_command="npm run type-check",
                success_condition="All imports resolve",
                failure_impact="Module not found error at runtime",
                is_blocking=True,
            ))
        
        return validations

    def _identify_mutation_risks(
        self,
        mutation_type: str,
        target_files: List[str],
    ) -> List[MutationRisk]:
        """Identify risks specific to this mutation."""
        risks = []
        
        if mutation_type == "inject_component":
            risks.extend([
                MutationRisk(
                    risk_id="RC001",
                    description="Component may not match parent's expected interface",
                    severity="high",
                    affected_areas=target_files,
                    mitigation="Verify props and TypeScript types of parent",
                ),
                MutationRisk(
                    risk_id="RC002",
                    description="Styling may conflict with existing CSS",
                    severity="medium",
                    affected_areas=["CSS modules", "global styles"],
                    mitigation="Check for class name conflicts",
                ),
            ])
        
        elif mutation_type == "insert_import":
            risks.append(MutationRisk(
                risk_id="RI001",
                description="Circular import may occur",
                severity="high",
                affected_areas=target_files,
                mitigation="Trace dependency graph to check for cycles",
            ))
        
        elif mutation_type == "append_block":
            risks.extend([
                MutationRisk(
                    risk_id="RA001",
                    description="Code may reference undefined variables",
                    severity="high",
                    affected_areas=target_files,
                    mitigation="Check all symbols are in scope",
                ),
                MutationRisk(
                    risk_id="RA002",
                    description="Syntax error may break entire file",
                    severity="critical",
                    affected_areas=target_files,
                    mitigation="Validate syntax before appending",
                ),
            ])
        
        elif mutation_type == "create_new_file":
            risks.extend([
                MutationRisk(
                    risk_id="CF001",
                    description="File may not be imported by module system",
                    severity="medium",
                    affected_areas=["Import resolution"],
                    mitigation="Verify file path follows project conventions",
                ),
            ])
        
        # Common risks
        risks.append(MutationRisk(
            risk_id="COMMON001",
            description="Mutation may break existing tests",
            severity="medium",
            affected_areas=["Test files"],
            mitigation="Run test suite after mutation",
        ))
        
        return risks

    def _calculate_investigation_confidence(
        self,
        num_file_inspections: int,
        num_symbol_traces: int,
        num_risks: int,
    ) -> float:
        """Calculate confidence level based on plan depth."""
        # Confidence increases with investigation depth
        base = 0.5
        
        # Each file inspection adds confidence
        file_confidence = min(num_file_inspections * 0.1, 0.3)
        
        # Each symbol trace adds confidence
        symbol_confidence = min(num_symbol_traces * 0.05, 0.15)
        
        # More risks identified = more informed = higher confidence
        risk_confidence = min(num_risks * 0.02, 0.1)
        
        total = base + file_confidence + symbol_confidence + risk_confidence
        return min(total, 1.0)


def create_investigation_plan_generator(
    repo_map: Optional[Any] = None,
    semantic_engine: Optional[Any] = None,
    tool_reasoning: Optional[Any] = None,
) -> InvestigationPlanGenerator:
    """Create an investigation plan generator."""
    return InvestigationPlanGenerator(repo_map, semantic_engine, tool_reasoning)
