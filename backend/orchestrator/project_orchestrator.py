"""Public generation orchestrator facade.

The implementation lives in backend.orchestrator.generation.* so this module can stay
small and audit-friendly while preserving legacy imports.
"""

from backend.orchestrator.generation.context import GenerationContext
from backend.orchestrator.generation.lifecycle import (
    _active_source_dir,
    _copy_project_tree,
    _ecosystem_label,
    _get_allowed_dependencies,
    _initialize_modify_run_from_current_state,
    _log_error_async,
    _log_work_async,
    _sync_run_to_latest,
)
from backend.orchestrator.generation.scaffold_phase import (
    _create_governance_files,
    _inject_truth_markers,
    scaffold_generation_workspace,
)
from backend.orchestrator.generation.project_state_phase import load_project_state_phase
from backend.orchestrator.generation.validation_phase import (
    _extract_served_run_marker,
    _filter_react_vite_generated_files,
    _first_error_code,
    _intent_requirements,
    _validate_dependency_resolution_environment,
    _validate_preview_usability,
    _validate_react_vite_environment,
    verify_rendered_dom_truth,
)
from backend.orchestrator.generation.collision_recovery_phase import (
    _background_values,
    _preservation_violations,
    consolidate_app_tsx,
    extract_app_tsx_metadata,
)
from backend.orchestrator.generation.orchestrator import generate_project_async

__all__ = [
    "GenerationContext",
    "generate_project_async",
    "_active_source_dir",
    "_copy_project_tree",
    "_ecosystem_label",
    "_get_allowed_dependencies",
    "_initialize_modify_run_from_current_state",
    "_log_error_async",
    "_log_work_async",
    "_sync_run_to_latest",
    "_create_governance_files",
    "_inject_truth_markers",
    "scaffold_generation_workspace",
    "load_project_state_phase",
    "_extract_served_run_marker",
    "_filter_react_vite_generated_files",
    "_first_error_code",
    "_intent_requirements",
    "_validate_dependency_resolution_environment",
    "_validate_preview_usability",
    "_validate_react_vite_environment",
    "verify_rendered_dom_truth",
    "_background_values",
    "_preservation_violations",
    "consolidate_app_tsx",
    "extract_app_tsx_metadata",
]
