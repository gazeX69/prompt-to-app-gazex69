"""
MinimalMutationPlanner

Prioritizes minimal edits over broad rewrites.

Prefer:
- insert_import
- inject_component
- append_block

Avoid:
- full file replacement
- broad rewrites
"""

import logging
import re
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EditStrategy(str, Enum):
    """Strategy for minimal mutation."""
    INSERT_IMPORT = "insert_import"  # Add import to top
    INSERT_EXPORT = "insert_export"  # Add export statement
    INJECT_COMPONENT = "inject_component"  # Add component to JSX
    APPEND_BLOCK = "append_block"  # Add code block to end
    PREPEND_BLOCK = "prepend_block"  # Add code block to start
    INSERT_HOOK = "insert_hook"  # Hook into existing function
    INJECT_MIDDLEWARE = "inject_middleware"  # Add middleware
    MODIFY_MINIMAL = "modify_minimal"  # Minimal targeted change
    CREATE_NEW_FILE = "create_new_file"  # Only if necessary


@dataclass
class MutationEdit:
    """Represents a single minimal edit."""
    strategy: EditStrategy
    target_file: str
    location: str  # 'top', 'bottom', 'after_line_N', 'before_symbol_X'
    code_to_insert: str
    line_number: Optional[int] = None
    dependency_locality: int = 3  # 1=isolated, 5=high ripple (default neutral)
    
    def __str__(self):
        return f"{self.strategy.value} at {self.target_file}:{self.location} (locality={self.dependency_locality})"


@dataclass
class MutationPlan:
    """Complete minimal mutation plan."""
    description: str
    total_files_affected: int
    edits: List[MutationEdit]
    file_order: List[str]  # order to apply edits
    validation_after_edit: List[str]  # commands to validate after each edit
    rollback_commands: List[str]  # how to undo if something breaks
    max_dependency_locality: int = 3  # 1=isolated, 5=high ripple
    impact_assessments: Dict[str, Any] = field(default_factory=dict)  # P8.5: per-file impacts
    structural_risks: Dict[str, Any] = field(default_factory=dict)  # P8.5: structural analysis
    
    def estimate_risk(self) -> str:
        """Estimate mutation risk level."""
        # Base risk from mutation type
        if len(self.edits) == 1 and self.edits[0].strategy in [
            EditStrategy.INSERT_IMPORT,
            EditStrategy.APPEND_BLOCK,
        ]:
            base_risk = "low"
        elif any(e.strategy == EditStrategy.MODIFY_MINIMAL for e in self.edits):
            base_risk = "medium"
        else:
            base_risk = "high"
        
        # Adjust for dependency locality
        if self.max_dependency_locality >= 4:
            # High ripple: escalate risk
            if base_risk == "low":
                base_risk = "medium"
            elif base_risk == "medium":
                base_risk = "high"
        
        return base_risk
    
    def total_lines_affected(self) -> int:
        """Count total lines across all edits."""
        return sum(len(e.code_to_insert.split('\n')) for e in self.edits)
    
    def prefer_isolated_edits(self) -> bool:
        """Check if all edits are on isolated modules."""
        return all(e.dependency_locality <= 2 for e in self.edits)


class MinimalMutationPlanner:
    """
    Plans mutations to minimize code changes.
    
    Core principles:
    1. Insert imports at top (non-intrusive)
    2. Inject components as children (localized)
    3. Append new functions at end (doesn't affect existing)
    4. Hook into existing functions only if necessary
    5. Never replace entire files unless absolutely required
    """

    def __init__(self, repo_map: Optional[Any] = None):
        self.repo_map = repo_map

    def plan_add_import(
        self,
        target_file: str,
        import_statement: str,
        after_existing_imports: bool = True,
    ) -> MutationPlan:
        """
        Plan adding an import statement.
        
        Minimal strategy: insert after last existing import.
        """
        plan = MutationPlan(
            description=f"Add import to {target_file}",
            total_files_affected=1,
            edits=[
                MutationEdit(
                    strategy=EditStrategy.INSERT_IMPORT,
                    target_file=target_file,
                    location="after_imports",
                    code_to_insert=import_statement,
                )
            ],
            file_order=[target_file],
            validation_after_edit=[
                "npm run type-check",
                "npm run lint -- --fix",
            ],
            rollback_commands=[
                f"git checkout {target_file}",
            ],
        )
        self._apply_locality_to_plan(plan)
        return plan

    def plan_inject_react_component(
        self,
        parent_file: str,
        component_code: str,
        component_name: str,
        inject_after_element: Optional[str] = None,
        pass_props: Optional[Dict[str, str]] = None,
    ) -> MutationPlan:
        """
        Plan injecting a React component into parent.
        
        Minimal strategy: inject as last child in parent render.
        """
        # Build component injection JSX
        props_str = ""
        if pass_props:
            props_str = " ".join(f'{k}={v}' for k, v in pass_props.items())
        
        injection = f"<{component_name}{' ' + props_str if props_str else ''} />"
        
        return MutationPlan(
            description=f"Inject {component_name} into {parent_file}",
            total_files_affected=1,
            edits=[
                MutationEdit(
                    strategy=EditStrategy.INJECT_COMPONENT,
                    target_file=parent_file,
                    location="last_child_in_render",
                    code_to_insert=injection,
                )
            ],
            file_order=[parent_file],
            validation_after_edit=[
                "npm run type-check",
                "npm run build 2>&1 | head -30",
            ],
            rollback_commands=[
                f"git checkout {parent_file}",
            ],
        )

    def plan_append_function(
        self,
        target_file: str,
        function_code: str,
        function_name: str,
    ) -> MutationPlan:
        """
        Plan appending a new function at end of file.
        
        Minimal strategy: append after last function.
        """
        return MutationPlan(
            description=f"Add {function_name} function to {target_file}",
            total_files_affected=1,
            edits=[
                MutationEdit(
                    strategy=EditStrategy.APPEND_BLOCK,
                    target_file=target_file,
                    location="end_of_file",
                    code_to_insert="\n\n" + function_code,
                )
            ],
            file_order=[target_file],
            validation_after_edit=[
                "npm run lint -- --fix",
                "npm run type-check",
            ],
            rollback_commands=[
                f"git checkout {target_file}",
            ],
        )

    def plan_add_api_endpoint(
        self,
        routes_file: str,
        endpoint_code: str,
        method: str,
        path: str,
    ) -> MutationPlan:
        """
        Plan adding API endpoint.
        
        Minimal strategy: append to routes file.
        """
        return MutationPlan(
            description=f"Add {method} {path} endpoint",
            total_files_affected=1,
            edits=[
                MutationEdit(
                    strategy=EditStrategy.APPEND_BLOCK,
                    target_file=routes_file,
                    location="before_export",
                    code_to_insert="\n\n" + endpoint_code,
                )
            ],
            file_order=[routes_file],
            validation_after_edit=[
                "npm run lint",
                "npm run type-check",
            ],
            rollback_commands=[
                f"git checkout {routes_file}",
            ],
        )

    def plan_create_component(
        self,
        component_path: str,
        component_code: str,
        component_name: str,
    ) -> MutationPlan:
        """
        Plan creating a new component file.
        
        Strategy: create file only if component doesn't exist elsewhere.
        """
        return MutationPlan(
            description=f"Create {component_name} component at {component_path}",
            total_files_affected=1,
            edits=[
                MutationEdit(
                    strategy=EditStrategy.CREATE_NEW_FILE,
                    target_file=component_path,
                    location="new_file",
                    code_to_insert=component_code,
                )
            ],
            file_order=[component_path],
            validation_after_edit=[
                "npm run type-check",
                "npm run build 2>&1 | head -30",
            ],
            rollback_commands=[
                f"rm {component_path}",
            ],
        )

    def plan_update_package_json(
        self,
        dependencies: Dict[str, str],
        dev_dependencies: Optional[Dict[str, str]] = None,
    ) -> MutationPlan:
        """
        Plan updating package.json with new dependencies.
        
        Minimal strategy: append to dependencies object, not full replacement.
        """
        edits = []
        
        if dependencies:
            edits.append(MutationEdit(
                strategy=EditStrategy.MODIFY_MINIMAL,
                target_file="package.json",
                location="in_dependencies",
                code_to_insert=self._format_deps(dependencies),
            ))
        
        if dev_dependencies:
            edits.append(MutationEdit(
                strategy=EditStrategy.MODIFY_MINIMAL,
                target_file="package.json",
                location="in_devDependencies",
                code_to_insert=self._format_deps(dev_dependencies),
            ))
        
        return MutationPlan(
            description="Update package.json dependencies",
            total_files_affected=1,
            edits=edits,
            file_order=["package.json"],
            validation_after_edit=[
                "npm install --no-save",
            ],
            rollback_commands=[
                "git checkout package.json",
                "git checkout package-lock.json 2>/dev/null || true",
            ],
        )

    def rank_strategies(
        self,
        available_strategies: List[EditStrategy],
    ) -> List[EditStrategy]:
        """
        Rank strategies by minimal-impact order.
        
        Order of preference:
        1. INSERT_IMPORT - trivial, non-intrusive
        2. APPEND_BLOCK - adds to end, doesn't touch existing
        3. CREATE_NEW_FILE - isolated, no existing code affected
        4. INJECT_COMPONENT - localized impact
        5. INSERT_HOOK - requires understanding existing function
        6. MODIFY_MINIMAL - requires precision
        7. PREPEND_BLOCK - affects line numbers
        8. INJECT_MIDDLEWARE - affects flow
        """
        ranking = [
            EditStrategy.INSERT_IMPORT,
            EditStrategy.APPEND_BLOCK,
            EditStrategy.CREATE_NEW_FILE,
            EditStrategy.INJECT_COMPONENT,
            EditStrategy.INSERT_HOOK,
            EditStrategy.MODIFY_MINIMAL,
            EditStrategy.PREPEND_BLOCK,
            EditStrategy.INJECT_MIDDLEWARE,
        ]
        
        # Return available strategies in preference order
        ranked = [s for s in ranking if s in available_strategies]
        # Add any others that aren't in the list
        ranked.extend([s for s in available_strategies if s not in ranked])
        return ranked

    def should_create_new_file(
        self,
        symbol_name: str,
        existing_locations: List[str],
    ) -> bool:
        """
        Determine if creating new file is better than modifying existing.
        
        Create new if:
        - Symbol doesn't exist anywhere
        - All existing locations would create coupling
        """
        if not existing_locations:
            return True
        
        # If there are existing locations, prefer injecting into one
        # Only create new if the existing ones are in completely different layers
        return False

    # ========== PRIVATE HELPERS ==========

    def _format_deps(self, deps: Dict[str, str]) -> str:
        """Format dependencies for insertion."""
        lines = []
        for name, version in deps.items():
            lines.append(f'    "{name}": "{version}",')
        return '\n'.join(lines)

    def _find_last_import_line(self, content: str) -> int:
        """Find line number of last import statement."""
        lines = content.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'require(')):
                last_import = i
        return last_import

    def _find_render_insertion_point(self, content: str) -> str:
        """Find where to insert component in JSX."""
        # Look for closing tag of main render container
        if 'return (' in content:
            # Find the outermost closing paren
            return "before_return_end"
        elif '<div' in content:
            return "before_div_close"
        else:
            return "end_of_render"

    def _generate_rollback(self, edit: MutationEdit) -> str:
        """Generate rollback command for an edit."""
        if edit.strategy == EditStrategy.CREATE_NEW_FILE:
            return f"rm {edit.target_file}"
        else:
            return f"git checkout {edit.target_file}"

    def _compute_dependency_locality(self, target_file: str) -> int:
        """
        Compute dependency locality score for a target file.
        
        Returns: 1=isolated, 5=high ripple
        """
        if not self.repo_map or not hasattr(self.repo_map, 'dependency_ripples'):
            # Heuristic-based fallback
            if any(part in target_file for part in ['core', 'shared', 'utils', '__init__']):
                return 4
            if any(part in target_file for part in ['components', 'features', 'pages']):
                return 2
            return 3  # neutral
        
        ripple = self.repo_map.dependency_ripples.get(target_file)
        if not ripple:
            return 3  # unknown = neutral
        
        # Map ripple depth to locality score
        locality = min(5, max(1, ripple.ripple_depth + 1))
        if ripple.is_critical:
            locality = min(5, locality + 1)
        
        return locality

    def _apply_locality_to_plan(self, plan: MutationPlan) -> None:
        """Apply dependency locality scores to all edits in a plan."""
        max_locality = 1
        
        for edit in plan.edits:
            edit.dependency_locality = self._compute_dependency_locality(edit.target_file)
            max_locality = max(max_locality, edit.dependency_locality)
        
        plan.max_dependency_locality = max_locality


def create_minimal_mutation_planner(
    repo_map: Optional[Any] = None,
) -> MinimalMutationPlanner:
    """Create a minimal mutation planner."""
    return MinimalMutationPlanner(repo_map)
