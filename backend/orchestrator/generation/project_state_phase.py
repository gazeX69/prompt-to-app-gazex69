import logging
from typing import Any

from backend.memory.project_memory import ProjectMemory
from backend.memory.workspace_awareness import WorkspaceAwareness
from backend.reflection.reflection_engine import ReflectionEngine
from backend.sockets.manager import emit_terminal_line

from .lifecycle import _initialize_modify_run_from_current_state

logger = logging.getLogger(__name__)


async def load_project_state_phase(
    req: Any,
    run_id: str,
    skill_name: str,
    *,
    initialize_modify_run=_initialize_modify_run_from_current_state,
) -> dict[str, Any]:
    ProjectMemory.initialize_project(req.project_id, skill_name)
    project_action = ProjectMemory.classify_action(req.project_id, req.prompt)
    project_state = ProjectMemory.load_for(req.project_id, "generation", ecosystem=skill_name)
    project_state_context = ProjectMemory.build_state_context(req.project_id, req.prompt)
    await emit_terminal_line("[ProjectState] Loaded for generation", "info", req.project_id)
    for key in ["project_type", "domain", "database", "supplier"]:
        if key in (project_state or {}):
            value = project_state.get(key)
            if isinstance(value, bool):
                value = str(value).lower()
            await emit_terminal_line(f"[ProjectState] {key}={value}", "info", req.project_id)
    await emit_terminal_line(
        f"[ProjectState] action={project_action.get('action')} inheritance={project_action.get('state_inheritance')} clean_prompt={project_action.get('clean_prompt')!r}",
        "info",
        req.project_id,
    )
    logger.info(
        "[ProjectState] action=%s inheritance=%s existing_type=%s clean_prompt=%r",
        project_action.get("action"),
        project_action.get("state_inheritance"),
        (project_state or {}).get("project_type"),
        project_action.get("clean_prompt"),
    )
    initialized_from_current_state = initialize_modify_run(req.project_id, run_id, project_action)
    if initialized_from_current_state:
        await emit_terminal_line(
            "[StatePreservation] MODIFY run initialized from active/latest project state.",
            "info",
            req.project_id,
        )
    workspace_awareness = WorkspaceAwareness.scan(req.project_id, run_id=run_id, prompt=req.prompt)
    await emit_terminal_line("[ProjectState] Loaded for workspace awareness", "info", req.project_id)
    await emit_terminal_line("[ProjectState] Loaded for reflection", "info", req.project_id)
    ReflectionEngine.predictive_reflection(req.project_id, req.prompt, workspace_awareness)
    workspace_awareness_context = WorkspaceAwareness.build_context(req.project_id, run_id=run_id, prompt=req.prompt)
    change_scope = None
    change_scope_context = ""
    try:
        from backend.brain.change_scope import ChangeScopeAnalyzer

        change_scope = ChangeScopeAnalyzer.analyze(
            req.project_id,
            req.prompt,
            project_state=project_state,
            project_action=project_action,
            workspace_awareness=workspace_awareness,
        )
        change_scope_context = ChangeScopeAnalyzer.build_context(req.project_id, req.prompt, change_scope)
        await emit_terminal_line(
            f"[ChangeScope] mode={change_scope.get('mode')} scope={change_scope.get('scope_size')} type={change_scope.get('change_type')} confidence={float(change_scope.get('confidence') or 0):.2f}",
            "info",
            req.project_id,
        )
    except Exception as e:
        logger.exception("Failed to analyze change scope for project=%s", req.project_id)
        await emit_terminal_line(f"[ChangeScope] Analysis skipped: {e}", "warning", req.project_id)

    return {
        "project_action": project_action,
        "project_state": project_state,
        "project_state_context": project_state_context,
        "initialized_from_current_state": initialized_from_current_state,
        "workspace_awareness": workspace_awareness,
        "workspace_awareness_context": workspace_awareness_context,
        "change_scope": change_scope,
        "change_scope_context": change_scope_context,
    }
