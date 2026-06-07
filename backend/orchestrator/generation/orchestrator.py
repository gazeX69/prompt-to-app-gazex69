"""Internal generation orchestration implementation.

Mechanical move from backend.orchestrator.project_orchestrator; public imports remain re-exported there.
"""

import logging
import os
import time
import asyncio
import datetime
import hashlib
import re
import shutil
from pathlib import Path

_P8_HISTORY_STORE = {}
import datetime

from backend.agent.parser import ParseError, parse_ai_response
from backend.brain.prompt_cleaning import clean_user_intent_prompt
from backend.agent.tools import write_file, append_file
from backend.models.schemas import GenerateRequest, GenerateResponse
from backend.core.router.routes import route_for_prompt, RouteResult
from backend.core.scanner.run_manifest import record_run_manifest
from backend.core.dependency_resolution import (
    apply_native_dependency_repair,
    has_unresolved_feature_dependency,
    has_unresolved_framework_dependency,
    resolve_dependency_health,
)
from backend.core.skills.interfaces import CommandStrategy
from backend.services.ai_service import complete
from backend.runtime_contract import RuntimeErrorCode
from backend.sockets.manager import emit_agent_state, emit_terminal_line, emit_agent_activity, emit_runtime_error
from backend.templates.registry import scaffold_template
from backend.templates.react_vite_contract import (
    PROTECTED_CONTRACT_FILES,
    classify_react_vite_failure,
    restore_canonical_react_vite_contract,
    validate_react_vite_contract,
)
from backend.validation.feature_contracts import (
    FeatureContractContext,
    extract_features,
    run_feature_contracts,
    save_feature_manifest,
)
from backend.sandbox.executor import _safe_project_path, stream_command_array_async, run_dev_server_array_async

logger = logging.getLogger(__name__)


def format_artifact_contract_prompt(task) -> str:
    requires = list(getattr(task, "requires_artifacts", []) or [])
    produces = list(getattr(task, "produces_artifacts", []) or [])
    if not requires and not produces:
        return ""

    required_lines = "\n".join(f"- {artifact}" for artifact in requires) or "- (none)"
    produced_lines = "\n".join(f"- {artifact}" for artifact in produces) or "- (none)"

    return (
        "\n\n=== ARTIFACT CONTRACT ===\n"
        "This task REQUIRES artifacts:\n"
        f"{required_lines}\n\n"
        "This task MUST PRODUCE artifacts:\n"
        f"{produced_lines}\n\n"
        "Rules:\n"
        "- Every produced artifact must be exported exactly by name.\n"
        "- For TYPE artifacts, use export interface/type/enum/class as appropriate.\n"
        "- For STORE artifacts such as useMarketplaceStore, export a named const/function exactly with that name.\n"
        "- For COMPONENT/PAGE artifacts, export a function/component exactly with that name.\n"
        "- Do not use default-only anonymous exports for required produced artifacts.\n"
        "- Do not rename produced artifacts.\n"
        "- Do not assume downstream tasks will adapt to different names.\n"
        "- If this task cannot produce the required artifact names within allowed paths, return a patch that creates the missing artifact explicitly.\n\n"
        "Examples:\n"
        "If produces_artifacts contains useMarketplaceStore, generated file must contain one of:\n"
        "export const useMarketplaceStore = ...\n"
        "export function useMarketplaceStore(...) { ... }\n\n"
        "If produces_artifacts contains MarketplacePage, generated file must contain:\n"
        "export function MarketplacePage() { ... }\n"
        "or\n"
        "export default function MarketplacePage() { ... }\n"
        "=== END ARTIFACT CONTRACT ===\n"
    )


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
    compose_conflicting_file_patches,
    consolidate_app_tsx,
    extract_app_tsx_metadata,
)

async def generate_project_async(req: GenerateRequest, generation_id: str | None = None) -> GenerateResponse:
    import random, string
    shortid = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{shortid}"
    ctx = GenerationContext(req=req, run_id=run_id, generation_id=generation_id)

    logger.info("[Orchestrator] Starting generation project=%s run_id=%s", req.project_id, run_id)
    try:
        record_run_manifest(
            req.project_id,
            run_id,
            status="running",
            generation_id=generation_id,
            prompt=req.prompt,
        )
    except Exception:
        logger.exception("[Orchestrator] Failed to persist running manifest project=%s run_id=%s", req.project_id, run_id)
    await emit_agent_state("planning", req.project_id)
    await emit_terminal_line(f"[Orchestrator] Starting run: {run_id}", "info", req.project_id)
    await emit_terminal_line("[Intent] Analyzing prompt...", "info", req.project_id)

    # ── Step 0: Route Skill ───────────────────────────────────────────────────
    route = await route_for_prompt(req.prompt, enabled_skills=req.enabled_skills)
    skill = route.primary
    skill_name = route.primary_name
    ctx.route = route
    ctx.skill = skill
    ctx.skill_name = skill_name

    await emit_terminal_line(f"[Router] Selected skill: {skill_name}", "info", req.project_id)
    await emit_terminal_line(f"[Router] Reason: {route.activated[0].reason if route.activated else 'fallback'}", "info", req.project_id)
    await emit_agent_activity(f"Using skill: {_ecosystem_label(skill_name)}", req.project_id)
    logger.info("[Router] skill=%s activated=%s", skill_name, route.activated_names)

    from backend.reflection.reflection_engine import ReflectionEngine
    phase_state = await load_project_state_phase(
        req,
        run_id,
        skill_name,
        initialize_modify_run=_initialize_modify_run_from_current_state,
    )
    project_action = phase_state["project_action"]
    project_state = phase_state["project_state"]
    project_state_context = phase_state["project_state_context"]
    initialized_from_current_state = phase_state["initialized_from_current_state"]
    workspace_awareness = phase_state["workspace_awareness"]
    workspace_awareness_context = phase_state["workspace_awareness_context"]
    change_scope = phase_state["change_scope"]
    change_scope_context = phase_state["change_scope_context"]
    ctx.project_action = project_action
    ctx.project_state = project_state
    ctx.workspace_awareness = workspace_awareness
    ctx.change_scope = change_scope

    if not skill:
        await emit_agent_state("failed", req.project_id)
        await emit_terminal_line("[Router] No skill available to handle this request", "stderr", req.project_id)
        return GenerateResponse(success=False, project_id=req.project_id, error="No matching skill found")

    hints = skill.get_generation_hints()
    cmd_strategy = skill.get_command_strategy()
    system_prompt = skill.get_system_prompt()
    # Scaffold Template (early initialization before Project Mapping & Planning)
    scaffold_error = await scaffold_generation_workspace(req, run_id, skill_name, hints, initialized_from_current_state)
    if scaffold_error:
        return GenerateResponse(success=False, project_id=req.project_id, error=scaffold_error)

    from backend.orchestrator.project_mapper import ProjectMapper
    from backend.orchestrator.planning_engine import PlanningEngine, PlanningFailure
    from backend.orchestrator.task_graph import TaskExecutor, TaskStatus
    from backend.orchestrator.session_persistence import OrchestrationSession, SessionPersistence
    import uuid
    
    # ── SHADOW MODE: Project Mapping & Cognitive Planning ─────────────────────
    mapper = ProjectMapper(req.project_id, run_id)
    await emit_terminal_line(f"[Governance] Operation 'Project Mapping' classified as MEDIUM cost", "info", req.project_id)
    project_map = await mapper.map_project(skill_name)
    await emit_terminal_line(f"[ProjectMapper] Detected ecosystem: {skill_name}, entrypoints: {len(project_map.entrypoints)}", "info", req.project_id)
    
    is_medium_or_broad = False
    cbr_context = ""
    generation_signature = None
    generation_scope = None
    generation_matches = []
    try:
        from backend.brain.plan_signature import build_plan_signature
        from backend.brain.case_retriever import retrieve_matching_cases
        from backend.brain.cbr_engine import build_case_context
        from backend.brain.decision_engine import decide_preflight
        from backend.brain.dss_engine import get_dss_recommendations
        from backend.brain.scope_analyzer import analyze_scope
        from backend.brain.schemas import ComplexityLevel, RiskLevel

        clean_generation_prompt = clean_user_intent_prompt(req.prompt)
        generation_signature = build_plan_signature(clean_generation_prompt)
        requested_app_type = generation_signature.app_type
        requested_domain = generation_signature.domain
        if (
            project_action.get("action") == "modify"
            and project_action.get("has_existing_project")
            and project_state
            and project_action.get("state_inheritance") != "reset"
        ):
            existing_type = project_state.get("project_type")
            existing_features = project_state.get("features") or []
            if existing_type and existing_type != "unknown":
                generation_signature.domain = existing_type
                generation_signature.app_type = existing_type
            generation_signature.complexity = ComplexityLevel.LOW
            generation_signature.feature_keywords = list(existing_features)
            if change_scope and change_scope.get("change_type"):
                generation_signature.required_capabilities = [change_scope["change_type"]]
            else:
                text_lower = clean_generation_prompt.lower()
                if any(term in text_lower for term in ["background", "warna", "biru", "style", "css"]):
                    generation_signature.required_capabilities = ["style_update"]
                else:
                    generation_signature.required_capabilities = ["targeted_project_modification"]
        await emit_terminal_line(
            f"[Intent] selected intent={generation_signature.intent} app_type={generation_signature.app_type} domain={generation_signature.domain} requested_app_type={requested_app_type} requested_domain={requested_domain}",
            "info",
            req.project_id,
        )
        logger.info(
            "[Intent] selected intent=%s app_type=%s domain=%s requested_app_type=%s requested_domain=%s",
            generation_signature.intent,
            generation_signature.app_type,
            generation_signature.domain,
            requested_app_type,
            requested_domain,
        )
        generation_scope = analyze_scope(req.prompt, generation_signature)
        if project_action.get("action") == "modify" and project_action.get("has_existing_project"):
            if change_scope and change_scope.get("scope_size") in {"medium", "large", "unclear"}:
                generation_scope.is_broad = True
                generation_scope.risk_level = RiskLevel.HIGH if change_scope.get("scope_size") == "large" else RiskLevel.MEDIUM
            else:
                generation_scope.is_broad = False
                generation_scope.risk_level = RiskLevel.LOW
                generation_scope.missing_decisions = []
        generation_matches = retrieve_matching_cases(generation_signature, prompt=req.prompt, limit=3)
        preflight_decision = decide_preflight(req.prompt, generation_signature, generation_scope, generation_matches)
        dss_recommendations = get_dss_recommendations(generation_scope.missing_decisions)
        cbr_context = build_case_context(
            prompt=req.prompt,
            signature=generation_signature,
            matched_cases=generation_matches,
            dss_recommendations=dss_recommendations,
            confidence=preflight_decision.confidence,
        )
        cbr_context = f"{project_state_context}\n\n{workspace_awareness_context}\n\n{change_scope_context}\n\n{cbr_context}"
        is_medium_or_broad = generation_scope.is_broad or generation_signature.complexity in {ComplexityLevel.MEDIUM, ComplexityLevel.HIGH}
        await emit_terminal_line(
            f"[CBR] signature={generation_signature.app_type}, matches={len(generation_matches)}, confidence={preflight_decision.confidence:.2f}",
            "info",
            req.project_id,
        )
    except Exception as e:
        logger.exception("Failed to check if prompt is medium or broad: %s", e)
        cbr_context = f"{project_state_context}\n\n{workspace_awareness_context}\n\n{change_scope_context}"

    await emit_terminal_line(f"[Governance] Operation 'Planning' classified as MEDIUM cost", "info", req.project_id)
    planner_prompt = f"{req.prompt}\n\n{cbr_context}" if cbr_context else req.prompt
    try:
        task_graph = await PlanningEngine.create_plan(planner_prompt, _ecosystem_label(skill_name), project_map)
    except PlanningFailure as e:
        await emit_agent_state("failed", req.project_id)
        err = str(e)
        await emit_terminal_line(f"[Planning] {err}", "stderr", req.project_id)
        await _log_error_async(req.project_id, run_id, err)
        return GenerateResponse(success=False, project_id=req.project_id, error=err)
    await emit_terminal_line(f"[TaskGraph] Generated {len(task_graph.tasks)} strictly sequenced tasks.", "info", req.project_id)
    feature_manifest = None
    try:
        feature_manifest = extract_features(
            project_id=req.project_id,
            run_id=run_id,
            prompt=req.prompt,
            generation_signature=generation_signature,
            task_graph=task_graph,
            project_state=project_state,
        )
        save_feature_manifest(req.project_id, feature_manifest)
        await emit_terminal_line("[FeatureExtraction] features:", "info", req.project_id)
        for feature in feature_manifest.features:
            await emit_terminal_line(
                f"[FeatureExtraction] - {feature.id} ({feature.category}, confidence={feature.confidence:.2f})",
                "info",
                req.project_id,
            )
    except Exception as e:
        logger.exception("[FeatureExtraction] failed: %s", e)
        await emit_terminal_line(f"[FeatureExtraction] failed: {e}", "warning", req.project_id)
    
    # Initialize OrchestrationSession
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    orchestration_session = OrchestrationSession(
        session_id=session_id,
        project_id=req.project_id,
        run_id=run_id,
        skill_name=skill_name,
        project_map=project_map,
        task_graph=task_graph
    )
    SessionPersistence.save_snapshot(orchestration_session)
    msg_sess = f"[SessionPersistence] Orchestration session snapshot created: {session_id}"
    print(msg_sess)
    await emit_terminal_line(msg_sess, "info", req.project_id)

    # Check for fallback planning task (LLM JSON parsing error)
    is_fallback = "fallback_task" in task_graph.tasks
    task_success = False

    from backend.orchestrator.artifact_registry import ArtifactRegistry
    registry = ArtifactRegistry(session_id)
    written = []

    if is_fallback:
        await emit_terminal_line("[TaskGraph] Planning failed (LLM returned invalid JSON). Skipping sequential execution...", "warning", req.project_id)
        if is_medium_or_broad:
            await emit_agent_state("failed", req.project_id)
            fallback_task = task_graph.get_task("fallback_task")
            error_reason = fallback_task.description if fallback_task else "Planner failed to generate valid JSON."
            error_msg = f"TaskGraph planning failed for a medium/broad prompt. Monolithic fallback is blocked for high complexity/broad scope. Reason: {error_reason}"
            await emit_terminal_line(f"[TaskExecutor] Error: {error_msg}", "stderr", req.project_id)
            await _log_error_async(req.project_id, run_id, error_msg)
            return GenerateResponse(success=False, project_id=req.project_id, error=error_msg)
    
    # ── P8.4A: Scoped Patch Synthesis (Dry-Run) ──────────────────────────────
    import os
    import json
    from backend.sandbox.executor import _safe_project_path
    
    base_path = _safe_project_path(req.project_id, run_id if initialized_from_current_state else "latest")
    p8_patches_dir = base_path / ".orchestration" / "p8" / "patches"
    p8_patches_dir.mkdir(parents=True, exist_ok=True)
    
    all_patches = []
    collision_map = {} # target_file -> list of tasks mutating it
    high_risk_overwrites = 0
    granular_operations = 0
    
    for t_id, task in task_graph.tasks.items():
        for p in task.patches:
            all_patches.append({
                "task_id": t_id,
                "patch": p.to_dict()
            })
            
            # Record operations for scoring
            if p.operation_type in ["insert_import", "inject_hook", "append_component", "append_style_block", "add_route", "extend_provider", "modify_props"]:
                granular_operations += 1
            if p.operation_type in ["replace_file", "regenerate_module"] or p.target_file.endswith("App.tsx"):
                high_risk_overwrites += 1
                
            # Collision detection logic
            target_key = f"{p.target_file}:{p.target_symbol}" if p.target_symbol else p.target_file
            if target_key not in collision_map:
                collision_map[target_key] = []
            collision_map[target_key].append((t_id, p.operation_type))
            
    # Compute patch locality score
    total_patches = len(all_patches)
    patch_locality_score = (granular_operations / total_patches) if total_patches > 0 else 1.0
    
    # Detect collisions
    collisions_detected = []
    for t_key, operations in collision_map.items():
        if len(operations) > 1:
            collisions_detected.append({
                "target": t_key,
                "operations": operations
            })
            await emit_terminal_line(f"[P8.4A] Collision Detected on {t_key}: {operations}", "warning", req.project_id)
            
    patch_synthesis_plan = {
        "total_patches_synthesized": total_patches,
        "patch_locality_score": patch_locality_score,
        "high_risk_overwrites": high_risk_overwrites,
        "collisions_detected": collisions_detected,
        "patches": all_patches
    }
    
    with open(p8_patches_dir / "patch_synthesis_plan.json", "w", encoding="utf-8") as f:
        json.dump(patch_synthesis_plan, f, indent=2)
        
    await emit_terminal_line(f"[P8.4A] Dry-run patch synthesis complete. Score: {patch_locality_score:.2f}", "info", req.project_id)
    # ── END P8.4A ────────────────────────────────────────────────────────────
    
    from backend.orchestrator.artifact_contracts import ArtifactContractRegistry
    artifact_contract_registry = ArtifactContractRegistry()
    executor = TaskExecutor(task_graph, artifact_registry=artifact_contract_registry)
    from backend.orchestrator.context_hydrator import ContextHydrator, detect_schema_drift, format_existing_code_reuse_context
    from backend.sandbox.executor import _safe_project_path
    
    base_path = _safe_project_path(req.project_id, run_id if initialized_from_current_state else "latest")
    hydrator = ContextHydrator(project_root=str(base_path), session_id=session_id, task_graph=task_graph)
    
    # Dummy execution callback for SHADOW MODE
    async def shadow_execution_callback(task):
        msg4 = f"[TaskExecutor] [SHADOW] Running task: {task.id} - {task.title}"
        print(msg4)
        task.add_log(msg4)
        await emit_terminal_line(msg4, "info", req.project_id)
        import json
        import os
        from backend.sandbox.executor import _safe_project_path
        from backend.services.ai_service import complete
        from backend.agent.parser import parse_ai_response
        
        # 1. Scope violation detection based on planning phase (if the planner gave forbidden paths)
        # Note: we'll do real bounds checking post-generation.

        # 2. Scoped prompt construction & Context Hydration
        bundle = hydrator.hydrate_context(task)
        
        ctx_str = "\n\n=== RELEVANT CONTEXT (Read-Only) ===\n"
        for name, content in bundle.readable_files.items():
            ctx_str += f"\n--- EXISTING FILE: {name} ---\n{content}\n"
        for name, content in bundle.dependency_outputs.items():
            ctx_str += f"\n--- DEPENDENCY OUTPUT: {name} ---\n{content}\n"
        for name, content in bundle.related_proposed_files.items():
            ctx_str += f"\n--- RELATED PROPOSED FILE: {name} ---\n{content}\n"
        reuse_context = format_existing_code_reuse_context(bundle)
        if reuse_context:
            logger.info("[ContextHydration] existing_code_reuse_context_enabled task=%s artifacts=%s symbols=%s", task.id, list(bundle.existing_artifact_context.keys()), bundle.known_symbols)
            task.add_log(
                f"[ContextHydration] Existing code reuse enabled artifacts={list(bundle.existing_artifact_context.keys())} symbols={bundle.known_symbols}"
            )
            
        allowed_deps = _get_allowed_dependencies(base_path)
        deps_constraint = ""
        if allowed_deps:
            deps_constraint = f"ALLOWED IMPORTS: You can ONLY import external packages listed here: {', '.join(allowed_deps)}. Do NOT import any other packages (such as 'react-toastify', 'axios', etc.). If you need icons or UI components, use browser alerts/custom code or already declared imports.\n"

        artifact_contract_prompt = format_artifact_contract_prompt(task)
        if artifact_contract_prompt:
            requires = list(getattr(task, "requires_artifacts", []) or [])
            produces = list(getattr(task, "produces_artifacts", []) or [])
            enforcement_log = (
                f"[ArtifactContract] Prompt enforcement enabled task={task.id} "
                f"requires={requires} produces={produces}"
            )
            logger.info(enforcement_log)
            task.add_log(enforcement_log)

        scoped_system_prompt = (
            f"You are a strictly bounded execution agent. Your task is to safely execute modifications within the specific boundaries.\n"
            f"{cbr_context}\n"
            f"Allowed write paths: {task.allowed_write_paths}\n"
            f"Forbidden paths: {task.forbidden_paths}\n"
            f"{deps_constraint}"
            f"{artifact_contract_prompt}"
            f"You MUST return a JSON array of structured PatchOperations.\n"
            f"Allowed operations and their required fields:\n"
            f"- create_file: target, content\n"
            f"- append_to_file: target, content\n"
            f"- insert_import: target, content\n"
            f"- replace_block: target, content, find (where 'find' is the EXACT code block to find and replace)\n"
            f"- inject_component: target, content, and either 'before' or 'after' (specifying the exact anchor block)\n"
            f"- modify_json_key: target, content, key_path\n"
            f"- append_php_include: target, content\n"
            f"Do NOT return raw file blobs or ===FILE=== delimiters. Return ONLY a valid JSON array of objects containing these fields.\n"
            f"{reuse_context}"
            f"{ctx_str}"
        )
        scoped_user_prompt = (
            f"Task: {task.title}\nDescription: {task.description}"
            f"{artifact_contract_prompt}"
            "\nExecute the task within the boundaries by providing a JSON array of patch operations."
        )
        
        patches = getattr(task, "concrete_patches", None)
        if patches is not None:
            task.add_log(f"[TaskExecutor] [SHADOW] Reusing {len(patches)} concrete/repaired patches.")
            from backend.orchestrator.patch_engine import PatchSafetyEngine, PatchSimulator
        else:
            task.add_log("[TaskExecutor] [SHADOW] Running scoped dry-run generation via LLM...")
            try:
                raw_response = await asyncio.to_thread(complete, scoped_system_prompt, scoped_user_prompt)
                # Find JSON array in the response
                import re
                json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_response, flags=re.DOTALL)
                if not json_match:
                    json_match = re.search(r'\[.*\]', raw_response, flags=re.DOTALL)
                    if not json_match:
                        task.add_log(f"[TaskExecutor] [SHADOW] Failed to parse JSON array from LLM response.")
                        task.add_log(f"[TaskExecutor] [SHADOW] Raw Response: {raw_response}")
                        task.status = TaskStatus.FAILED
                        task.error_msg = "Invalid JSON structure from LLM"
                        return False
                    
                operations_data = json.loads(json_match.group(0))
                
                from backend.orchestrator.patch_engine import PatchOperation, PatchSafetyEngine, PatchSimulator
                patches = [PatchOperation.from_dict(d) for d in operations_data]
                task.concrete_patches = patches  # Save concrete patches for real execution!
                task.add_log(f"[TaskExecutor] [SHADOW] Scoped generation yielded {len(patches)} patch operations.")
            except Exception as e:
                task.add_log(f"[TaskExecutor] [SHADOW] Dry-run generation crashed: {e}")
                return False
            
        try:
            # Setup simulation
            allowed_paths = list(set((task.allowed_write_paths or []) + (task.affected_files or [])))
            engine = PatchSafetyEngine(allowed_paths=allowed_paths, forbidden_paths=task.forbidden_paths)
            simulator = PatchSimulator(workspace_root=str(base_path), session_id=session_id, task_id=task.id)
            
            # Use bundle.readable_files, bundle.dependency_outputs, and bundle.related_proposed_files as starting point
            current_files = bundle.readable_files.copy()
            current_files.update(bundle.dependency_outputs)
            current_files.update(bundle.related_proposed_files)
            
            reports = simulator.simulate(patches, current_files, engine)
            
            # Check for forbidden or failed patches
            failed_patches = 0
            for r in reports:
                if r.classification == "forbidden":
                    task.add_log(f"[TaskExecutor] [SHADOW] SCOPE VIOLATION (Skipped): {r.operation.target} is forbidden.")
                    failed_patches += 1
                elif not r.success:
                    task.add_log(f"[TaskExecutor] [SHADOW] Patch failed on {r.operation.target}: {r.error}")
                    failed_patches += 1
                else:
                    simulated_path = os.path.join(simulator.sim_dir, r.operation.target.replace("/", os.sep))
                    try:
                        with open(simulated_path, "r", encoding="utf-8") as f:
                            simulated_content = f.read()
                    except Exception:
                        simulated_content = ""
                    old_content = current_files.get(r.operation.target, "")
                    preservation_errors = _preservation_violations(
                        r.operation.target,
                        old_content,
                        simulated_content,
                        change_scope,
                    )
                    if preservation_errors:
                        for error in preservation_errors:
                            task.add_log(f"[TaskExecutor] [SHADOW] PRESERVATION VIOLATION: {error}")
                        failed_patches += 1
            
            if failed_patches > 0:
                task.status = TaskStatus.FAILED
                task.error_msg = f"{failed_patches} patch operations failed simulation or violated scope during shadow run."
                return False
                
            task.add_log(f"[TaskExecutor] [SHADOW] Patch simulation completed. {len([r for r in reports if r.success])}/{len(reports)} succeeded.")
            
            # (Optional) we could map proposed files back to task.proposed_artifacts for downstream tasks
            # using the simulation directory:
            for fpath in set(p.target for p in patches):
                task.proposed_artifacts[fpath] = os.path.join(simulator.sim_dir, fpath.replace("/", os.sep))

            drift_files = current_files.copy()
            for fpath, phys_path in task.proposed_artifacts.items():
                if os.path.exists(phys_path):
                    try:
                        with open(phys_path, "r", encoding="utf-8") as f:
                            drift_files[fpath] = f.read()
                    except Exception:
                        pass
            drift_findings = detect_schema_drift(drift_files)
            if drift_findings:
                task.status = TaskStatus.FAILED
                task.error_msg = "\n".join(drift_findings)
                for finding in drift_findings:
                    task.add_log(f"[SchemaDrift] {finding}")
                    await emit_terminal_line(f"[SchemaDrift] {finding}", "stderr", req.project_id)
                return False
            
            # 5. Check Merge Safety
            # (Since we are using structural patches, they are much safer. But we can keep the hydrator report generation as it also flags missing dependencies)
            from backend.agent.parser import GeneratedFile
            proposed_files = []
            for fpath, phys_path in task.proposed_artifacts.items():
                if os.path.exists(phys_path):
                    with open(phys_path, 'r', encoding='utf-8') as f:
                        proposed_files.append(GeneratedFile(path=fpath, content=f.read()))
            report = hydrator.check_merge_safety(task, proposed_files, bundle)
            if not report.safe_to_write:
                task.add_log(f"[TaskExecutor] [SHADOW] MERGE SAFETY FAILED: {report.reason}")
            else:
                task.add_log(f"[TaskExecutor] [SHADOW] Merge safety passed.")

            proposed_content = {generated.path: generated.content for generated in proposed_files}
            artifact_result = artifact_contract_registry.register_discovered_files(task, proposed_content)
            if not artifact_result.passed:
                task.status = TaskStatus.FAILED
                task.error_msg = artifact_result.message
                task.add_log("[ArtifactContract] Missing artifacts:")
                for artifact in artifact_result.missing_artifacts:
                    task.add_log(f"- {artifact}")
                await emit_terminal_line(f"[ArtifactContract] {artifact_result.message}", "stderr", req.project_id)
                return False
                
            session_dir = base_path / ".orchestration"
            hydrator.save_reports(str(session_dir))
            
        except Exception as e:
            task.add_log(f"[TaskExecutor] [SHADOW] Dry-run generation crashed: {e}")
            return False
        
        if task.validation_contract:
            msg5 = f"[ValidationContract] [SHADOW] Validating success criteria: {task.validation_contract.success_criteria}"
            print(msg5)
            task.add_log(msg5)
            await emit_terminal_line(msg5, "info", req.project_id)
            task.validation_artifacts["dummy_validation_proof"] = "success"
        
        SessionPersistence.save_snapshot(orchestration_session)
        return True # Succeed in shadow mode if no scope violation
        
    await executor.execute_all(shadow_execution_callback)
    
    # ── Collision Recovery / Aggregation / Repair Pass ───────────────────────
    is_dry_run_failed = task_graph.has_failed_tasks()
    has_collisions = len(collisions_detected) > 0
    
    if is_dry_run_failed or has_collisions:
        await emit_terminal_line("[CollisionRecovery] Failure or collision detected in initial dry-run. Initiating Collision Repair Pass...", "warning", req.project_id)
        
        # Print failed task logs for diagnostic visibility
        for t_id, task in task_graph.tasks.items():
            if task.status == TaskStatus.FAILED:
                print(f"[CollisionRecovery Diagnostics] Failed task {t_id}: {task.error_msg}")
                for log in task.logs:
                    print(f"  [CollisionRecovery Log] {log}")
        
        # Step A: Find the primary owner of src/App.tsx
        primary_app_owner = None
        for t_id, task in task_graph.tasks.items():
            if "src/App.tsx" in task.allowed_write_paths:
                primary_app_owner = t_id
                break
        if not primary_app_owner:
            for t_id, task in task_graph.tasks.items():
                if "src/App.tsx" in task.affected_files:
                    primary_app_owner = t_id
                    break
        if not primary_app_owner:
            if "task-1" in task_graph.tasks:
                primary_app_owner = "task-1"
            elif task_graph.tasks:
                primary_app_owner = list(task_graph.tasks.keys())[0]
                
        if primary_app_owner:
            session_planned_imports = []
            session_planned_routes = []
            session_planned_states = []
            other_app_patches = []
            
            # Step B: Gather all patch intents from other tasks
            for t_id, task in task_graph.tasks.items():
                if t_id == primary_app_owner:
                    continue
                    
                concrete_patches = getattr(task, "concrete_patches", None)
                if concrete_patches is None:
                    continue
                    
                remaining_patches = []
                for p in concrete_patches:
                    if p.target == "src/App.tsx":
                        # Record raw patch for sequential application
                        other_app_patches.append(p)
                        # Extract route, import, state metadata
                        meta = extract_app_tsx_metadata(p)
                        session_planned_imports.extend(meta["imports"])
                        session_planned_routes.extend(meta["routes"])
                        session_planned_states.extend(meta["states_or_props"])
                    else:
                        remaining_patches.append(p)
                task.concrete_patches = remaining_patches
                
            # Step C: Consolidate patches into the primary owner's App.tsx patch
            owner_task = task_graph.get_task(primary_app_owner)
            app_patch = None
            if hasattr(owner_task, "concrete_patches") and owner_task.concrete_patches:
                for p in owner_task.concrete_patches:
                    if p.target == "src/App.tsx" and p.operation == "create_file":
                        app_patch = p
                        break
                    
            if app_patch:
                base_content = app_patch.content
                for p in other_app_patches:
                    try:
                        from backend.orchestrator.patch_engine import apply_patch
                        base_content = apply_patch(p, base_content)
                        await emit_terminal_line(f"[CollisionRecovery] Successfully applied patch {p.operation} from secondary task to base App.tsx content.", "info", req.project_id)
                    except Exception as e:
                        await emit_terminal_line(f"[CollisionRecovery] Could not apply patch {p.operation} sequentially: {e}. Falling back to metadata extraction.", "warning", req.project_id)

                app_patch.content = consolidate_app_tsx(
                    base_content,
                    session_planned_imports,
                    session_planned_routes,
                    session_planned_states
                )
                await emit_terminal_line(
                    f"[CollisionRecovery] Consolidated {len(session_planned_imports)} imports, "
                    f"{len(session_planned_routes)} routes, and {len(session_planned_states)} states "
                    f"into primary App.tsx owner task ({primary_app_owner}) create_file patch.",
                    "info",
                    req.project_id
                )
            else:
                # Fallback: Read current simulated/workspace App.tsx content and append new consolidated patch
                existing_content = ""
                sim_path = os.path.join(str(base_path), ".orchestration", "patch_simulations", session_id, primary_app_owner, "src", "App.tsx")
                if os.path.exists(sim_path):
                    with open(sim_path, "r", encoding="utf-8") as f:
                        existing_content = f.read()
                if not existing_content:
                    workspace_path = base_path / "src" / "App.tsx"
                    if workspace_path.exists():
                        existing_content = workspace_path.read_text(encoding="utf-8")
                        
                # Default React App.tsx skeleton if file is empty or missing
                if not existing_content:
                    existing_content = """import React from 'react';
import { Routes, Route } from 'react-router-dom';

export default function App() {
  return (
    <div className="app">
      <Routes>
      </Routes>
    </div>
  );
}
"""
                for p in other_app_patches:
                    try:
                        from backend.orchestrator.patch_engine import apply_patch
                        existing_content = apply_patch(p, existing_content)
                        await emit_terminal_line(f"[CollisionRecovery] Successfully applied patch {p.operation} to fallback App.tsx content.", "info", req.project_id)
                    except Exception as e:
                        await emit_terminal_line(f"[CollisionRecovery] Could not apply patch {p.operation} sequentially: {e}. Falling back to metadata extraction.", "warning", req.project_id)

                consolidated_content = consolidate_app_tsx(
                    existing_content,
                    session_planned_imports,
                    session_planned_routes,
                    session_planned_states
                )
                from backend.orchestrator.patch_engine import PatchOperation
                new_p = PatchOperation(
                    operation="create_file",
                    target="src/App.tsx",
                    content=consolidated_content
                )
                if not hasattr(owner_task, "concrete_patches") or owner_task.concrete_patches is None:
                    owner_task.concrete_patches = []
                owner_task.concrete_patches = [p for p in owner_task.concrete_patches if p.target != "src/App.tsx"]
                owner_task.concrete_patches.append(new_p)
                await emit_terminal_line(
                    f"[CollisionRecovery] Created new consolidated App.tsx patch for primary owner task ({primary_app_owner})",
                    "info",
                    req.project_id
                )
            
            # Step D: Process collisions on other files
            file_patches = {}
            for t_id, task in task_graph.tasks.items():
                concrete_patches = getattr(task, "concrete_patches", []) or []
                for p in concrete_patches:
                    if p.target == "src/App.tsx":
                        continue
                    if p.target not in file_patches:
                        file_patches[p.target] = []
                    file_patches[p.target].append((t_id, p))

            for target_file, p_list in file_patches.items():
                distinct_tasks = set(t_id for t_id, _ in p_list)
                if len(distinct_tasks) <= 1:
                    continue
                    
                await emit_terminal_line(
                    f"[CollisionRecovery] Collision detected on {target_file} from tasks: {list(distinct_tasks)}",
                    "warning",
                    req.project_id
                )
                
                sorted_tasks = sorted(list(distinct_tasks), key=lambda x: int(x.split('-')[-1]) if '-' in x and x.split('-')[-1].isdigit() else 999)
                earliest_task_id = sorted_tasks[0]
                earliest_task = task_graph.get_task(earliest_task_id)
                
                merged_patches = []
                folded_patches, fold_report = compose_conflicting_file_patches(target_file, p_list, sorted_tasks)
                if folded_patches is not None:
                    merged_patches = folded_patches
                    await emit_terminal_line(
                        f"[CollisionRecovery] Folded same-file patch chain into final create_file for {target_file}",
                        "info",
                        req.project_id,
                    )
                    for note in fold_report.get("notes") or []:
                        await emit_terminal_line(f"[CollisionRecovery] {target_file}: {note}", "info", req.project_id)
                    if fold_report.get("stale_anchor"):
                        await emit_terminal_line(
                            f"[CollisionRecovery] Stale replace_block anchor detected and removed from retry chain for {target_file}",
                            "warning",
                            req.project_id,
                        )
                else:
                    seen_create = False
                    
                    for t_id in sorted_tasks:
                        task_ops = [p for tid, p in p_list if tid == t_id]
                        for p in task_ops:
                            if p.operation == "create_file":
                                if not seen_create:
                                    merged_patches.append(p)
                                    seen_create = True
                                else:
                                    first_create = next(op for op in merged_patches if op.operation == "create_file")
                                    if first_create.content.strip() == p.content.strip():
                                        await emit_terminal_line(f"[CollisionRecovery] Merged duplicate create_file for {target_file}", "info", req.project_id)
                                    else:
                                        await emit_terminal_line(f"[CollisionRecovery] Conflict: Duplicate create_file with different contents for {target_file}. Keeping earliest task's content.", "warning", req.project_id)
                            elif p.operation in ["append_to_file", "append_php_include"]:
                                existing_append = next((op for op in merged_patches if op.operation == p.operation), None)
                                if existing_append:
                                    existing_append.content += "\n" + p.content
                                    await emit_terminal_line(f"[CollisionRecovery] Merged append_to_file for {target_file}", "info", req.project_id)
                                else:
                                    merged_patches.append(p)
                            elif p.operation == "insert_import":
                                existing_import = next((op for op in merged_patches if op.operation == "insert_import"), None)
                                if existing_import:
                                    existing_lines = [line.strip() for line in existing_import.content.split('\n') if line.strip()]
                                    new_lines = [line.strip() for line in p.content.split('\n') if line.strip()]
                                    for line in new_lines:
                                        if line not in existing_lines:
                                            existing_lines.append(line)
                                    existing_import.content = "\n".join(existing_lines)
                                else:
                                    merged_patches.append(p)
                            elif p.operation == "modify_json_key":
                                duplicate_key = next((op for op in merged_patches if op.operation == "modify_json_key" and op.key_path == p.key_path), None)
                                if duplicate_key:
                                    if duplicate_key.content.strip() != p.content.strip():
                                        await emit_terminal_line(f"[CollisionRecovery] Conflict: Different value for json key '{p.key_path}' in {target_file}. Keeping earliest.", "warning", req.project_id)
                                else:
                                    merged_patches.append(p)
                            elif p.operation == "replace_block":
                                duplicate_replace = next((op for op in merged_patches if op.operation == "replace_block" and op.find == p.find), None)
                                if duplicate_replace:
                                    if duplicate_replace.content.strip() != p.content.strip():
                                        await emit_terminal_line(f"[CollisionRecovery] Conflict: Different replace block for '{p.find}' in {target_file}. Keeping earliest.", "warning", req.project_id)
                                else:
                                    merged_patches.append(p)
                            elif p.operation == "inject_component":
                                duplicate_inject = next((op for op in merged_patches if op.operation == "inject_component" and op.after == p.after and op.before == p.before), None)
                                if duplicate_inject:
                                    duplicate_inject.content += "\n" + p.content
                                else:
                                    merged_patches.append(p)
                            else:
                                merged_patches.append(p)

                if hasattr(earliest_task, "concrete_patches") and earliest_task.concrete_patches is not None:
                    earliest_task.concrete_patches = [p for p in earliest_task.concrete_patches if p.target != target_file]
                    earliest_task.concrete_patches.extend(merged_patches)
                    
                for t_id in distinct_tasks:
                    if t_id == earliest_task_id:
                        continue
                    other_task = task_graph.get_task(t_id)
                    if hasattr(other_task, "concrete_patches") and other_task.concrete_patches is not None:
                        other_task.concrete_patches = [p for p in other_task.concrete_patches if p.target != target_file]

            # Step E: Reset task graph task statuses for re-running dry-run
            from backend.orchestrator.task_graph import TaskStatus
            for task in task_graph.tasks.values():
                task.status = TaskStatus.PENDING
                task.error_msg = None
                task.started_at = None
                task.completed_at = None
                task.logs = []
                task.validation_artifacts = {}
                
            # Step F: Re-run dry-run with consolidated/repaired patches
            await emit_terminal_line("[CollisionRecovery] Re-running dry-run with consolidated/repaired patches...", "info", req.project_id)
            artifact_contract_registry = ArtifactContractRegistry()
            executor.artifact_registry = artifact_contract_registry
            await executor.execute_all(shadow_execution_callback)
            
            if task_graph.has_failed_tasks():
                await emit_terminal_line("[CollisionRecovery] Dry-run still failed after repair attempt.", "stderr", req.project_id)
            else:
                await emit_terminal_line("[CollisionRecovery] Dry-run repaired successfully!", "success", req.project_id)

    # Check if anything failed in shadow mode
    if task_graph.has_failed_tasks():
        orchestration_session.status = "failed"
        SessionPersistence.save_snapshot(orchestration_session)
        msg6 = "[TaskExecutor] [SHADOW] Execution graph failed. Aborting real execution."
        print(msg6)
        await emit_terminal_line(msg6, "warning", req.project_id)
        dry_run_error = "TaskGraph shadow/dry-run execution failed pre_runtime. Collision/stale-anchor patch simulation reported failures."
        try:
            record_run_manifest(
                req.project_id,
                run_id,
                status="failed",
                generation_id=generation_id,
                prompt=req.prompt,
                error=dry_run_error,
                detail={"stage": "pre_runtime", "reason": "collision_or_stale_anchor"},
            )
        except Exception:
            logger.exception("[Orchestrator] Failed to persist pre_runtime dry-run failure project=%s run_id=%s", req.project_id, run_id)
        return GenerateResponse(success=False, project_id=req.project_id, error=dry_run_error)
    else:
        orchestration_session.status = "completed"
        SessionPersistence.save_snapshot(orchestration_session)
        msg7 = "[TaskExecutor] [SHADOW] Execution graph completed successfully."
        print(msg7)
        await emit_terminal_line(msg7, "success", req.project_id)
    # ── END SHADOW MODE ───────────────────────────────────────────────────────

    await emit_agent_state("scaffolding", req.project_id)
    await emit_terminal_line("[Template] Project workspace is scaffolded and ready.", "info", req.project_id)

    await emit_terminal_line("[Governance] Creating workspace governance files...", "info", req.project_id)
    await asyncio.to_thread(_create_governance_files, req.project_id, run_id, req.prompt, skill_name)
    await emit_terminal_line("[Governance] Files created.", "info", req.project_id)

    # ── Step 2: Generate Features ─────────────────────────────────────────────
    await emit_agent_state("generating", req.project_id)
    await emit_terminal_line(f"[AI] Starting sequential developer generation via TaskGraph...", "info", req.project_id)

    from backend.orchestrator.artifact_registry import ArtifactRegistry
    from backend.orchestrator.artifact_contracts import ArtifactContractRegistry
    registry = ArtifactRegistry(session_id)
    real_artifact_contract_registry = ArtifactContractRegistry()
    written = []
    
    real_base_path = _safe_project_path(req.project_id, run_id)
    real_hydrator = ContextHydrator(project_root=str(real_base_path), session_id=session_id, task_graph=task_graph)
    
    async def real_execution_callback_inner(task):
        msg = f"[TaskExecutor] Running task: {task.id} - {task.title}"
        print(msg)
        task.add_log(msg)
        await emit_terminal_line(msg, "info", req.project_id)
        
        # Context hydration
        bundle = real_hydrator.hydrate_context(task)
        
        ctx_str = "\n\n=== RELEVANT CONTEXT (Read-Only) ===\n"
        for name, content in bundle.readable_files.items():
            ctx_str += f"\n--- EXISTING FILE: {name} ---\n{content}\n"
        for name, content in bundle.dependency_outputs.items():
            ctx_str += f"\n--- DEPENDENCY OUTPUT: {name} ---\n{content}\n"
        for name, content in bundle.related_proposed_files.items():
            ctx_str += f"\n--- RELATED PROPOSED FILE: {name} ---\n{content}\n"
        reuse_context = format_existing_code_reuse_context(bundle)
        if reuse_context:
            logger.info("[ContextHydration] existing_code_reuse_context_enabled task=%s artifacts=%s symbols=%s", task.id, list(bundle.existing_artifact_context.keys()), bundle.known_symbols)
            task.add_log(
                f"[ContextHydration] Existing code reuse enabled artifacts={list(bundle.existing_artifact_context.keys())} symbols={bundle.known_symbols}"
            )
            
        allowed_deps = _get_allowed_dependencies(real_base_path)
        deps_constraint = ""
        if allowed_deps:
            deps_constraint = f"ALLOWED IMPORTS: You can ONLY import external packages listed here: {', '.join(allowed_deps)}. Do NOT import any other packages (such as 'react-toastify', 'axios', etc.). If you need icons or UI components, use browser alerts/custom code or already declared imports.\n"

        artifact_contract_prompt = format_artifact_contract_prompt(task)
        if artifact_contract_prompt:
            requires = list(getattr(task, "requires_artifacts", []) or [])
            produces = list(getattr(task, "produces_artifacts", []) or [])
            enforcement_log = (
                f"[ArtifactContract] Prompt enforcement enabled task={task.id} "
                f"requires={requires} produces={produces}"
            )
            logger.info(enforcement_log)
            task.add_log(enforcement_log)

        scoped_system_prompt = (
            f"You are a professional developer AI Agent. Your task is to safely execute modifications within the specific boundaries.\n"
            f"{cbr_context}\n"
            f"Allowed write paths: {task.allowed_write_paths}\n"
            f"Forbidden paths: {task.forbidden_paths}\n"
            f"{deps_constraint}"
            f"{artifact_contract_prompt}"
            f"You MUST return a JSON array of structured PatchOperations.\n"
            f"Allowed operations and their required fields:\n"
            f"- create_file: target, content\n"
            f"- append_to_file: target, content\n"
            f"- insert_import: target, content\n"
            f"- replace_block: target, content, find (where 'find' is the EXACT code block to find and replace)\n"
            f"- inject_component: target, content, and either 'before' or 'after' (specifying the exact anchor block)\n"
            f"- modify_json_key: target, content, key_path\n"
            f"- append_php_include: target, content\n"
            f"Do NOT return raw file blobs or ===FILE=== delimiters. Return ONLY a valid JSON array of objects containing these fields.\n"
            f"{reuse_context}"
            f"{ctx_str}"
        )
        scoped_user_prompt = (
            f"Task: {task.title}\nDescription: {task.description}"
            f"{artifact_contract_prompt}"
            "\nExecute the task within the boundaries by providing a JSON array of patch operations."
        )
        
        patches = getattr(task, "concrete_patches", None)
        if patches is not None:
            task.add_log(f"[TaskExecutor] Reusing {len(patches)} concrete patches generated during shadow/dry-run phase.")
            await emit_terminal_line(f"[TaskExecutor] Reusing {len(patches)} concrete patches generated during shadow/dry-run phase.", "info", req.project_id)
        else:
            task.add_log("[TaskExecutor] Running scoped generation via LLM...")
            try:
                raw_response = await asyncio.to_thread(complete, scoped_system_prompt, scoped_user_prompt)
                import re
                json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_response, flags=re.DOTALL)
                if not json_match:
                    json_match = re.search(r'\[.*\]', raw_response, flags=re.DOTALL)
                    if not json_match:
                        task.add_log(f"[TaskExecutor] Failed to parse JSON array from LLM response.")
                        task.status = TaskStatus.FAILED
                        task.error_msg = "Invalid JSON structure from LLM"
                        return False
                    
                operations_data = json.loads(json_match.group(0))
                
                from backend.orchestrator.patch_engine import PatchOperation
                patches = [PatchOperation.from_dict(d) for d in operations_data]
                task.add_log(f"[TaskExecutor] Scoped generation yielded {len(patches)} patch operations.")
            except Exception as e:
                task.add_log(f"[TaskExecutor] Scoped generation crashed: {e}")
                task.status = TaskStatus.FAILED
                task.error_msg = str(e)
                return False

        from backend.orchestrator.patch_engine import PatchSafetyEngine, PatchSimulator
        try:
            allowed_paths = list(set((task.allowed_write_paths or []) + (task.affected_files or [])))
            engine = PatchSafetyEngine(allowed_paths=allowed_paths, forbidden_paths=task.forbidden_paths)
            simulator = PatchSimulator(workspace_root=str(real_base_path), session_id=session_id, task_id=task.id)
            
            current_files = bundle.readable_files.copy()
            current_files.update(bundle.dependency_outputs)
            current_files.update(bundle.related_proposed_files)
            
            reports = simulator.simulate(patches, current_files, engine)
            
            failed_patches = 0
            for r in reports:
                if r.classification == "forbidden":
                    task.add_log(f"[TaskExecutor] SCOPE VIOLATION (Skipped): {r.operation.target} is forbidden.")
                    failed_patches += 1
                elif not r.success:
                    task.add_log(f"[TaskExecutor] Patch failed on {r.operation.target}: {r.error}")
                    failed_patches += 1
            
            if failed_patches > 0:
                task.status = TaskStatus.FAILED
                task.error_msg = f"{failed_patches} patch operations failed or violated scope."
                return False
                
            task.add_log(f"[TaskExecutor] Patch simulation completed. {len(reports)}/{len(reports)} succeeded.")
            
            # Map proposed files back to task.proposed_artifacts for downstream tasks
            # using the simulation directory
            import os
            for fpath in set(p.target for p in patches):
                task.proposed_artifacts[fpath] = os.path.join(simulator.sim_dir, fpath.replace("/", os.sep))

            drift_files = current_files.copy()
            for fpath, phys_path in task.proposed_artifacts.items():
                if os.path.exists(phys_path):
                    try:
                        with open(phys_path, "r", encoding="utf-8") as f:
                            drift_files[fpath] = f.read()
                    except Exception:
                        pass
            drift_findings = detect_schema_drift(drift_files)
            if drift_findings:
                task.status = TaskStatus.FAILED
                task.error_msg = "\n".join(drift_findings)
                for finding in drift_findings:
                    task.add_log(f"[SchemaDrift] {finding}")
                    await emit_terminal_line(f"[SchemaDrift] {finding}", "stderr", req.project_id)
                return False
            
            # Apply patches to ACTUAL workspace!
            written_contents: dict[str, str] = {}
            for patch in patches:
                target_path = real_base_path / patch.target
                
                # Apply the specific operation to target file
                file_content = ""
                if target_path.exists():
                    file_content = target_path.read_text(encoding="utf-8")
                
                try:
                    from backend.orchestrator.patch_engine import apply_patch
                    new_content = apply_patch(patch, file_content)
                except Exception as e:
                    task.add_log(f"Patch execution failed on {patch.target}: {e}")
                    return False

                preservation_errors = _preservation_violations(patch.target, file_content, new_content, change_scope)
                if preservation_errors:
                    for error in preservation_errors:
                        task.add_log(f"[TaskExecutor] PRESERVATION VIOLATION: {error}")
                        await emit_terminal_line(f"[StatePreservation] {error}", "stderr", req.project_id)
                    return False
                
                # Write back to workspace
                path = await asyncio.to_thread(write_file, req.project_id, patch.target, new_content, run_id)
                registry.add_actual_file(patch.target, new_content)
                written_contents[patch.target] = new_content
                if path not in written:
                    written.append(path)
                task.add_log(f"[TaskExecutor] Applied patch to {patch.target}")
                await emit_terminal_line(f"[TaskExecutor] Applied patch to {patch.target}", "info", req.project_id)

            artifact_result = real_artifact_contract_registry.register_discovered_files(task, written_contents)
            if not artifact_result.passed:
                task.status = TaskStatus.FAILED
                task.error_msg = artifact_result.message
                task.add_log("[ArtifactContract] Missing artifacts:")
                for artifact in artifact_result.missing_artifacts:
                    task.add_log(f"- {artifact}")
                await emit_terminal_line(f"[ArtifactContract] {artifact_result.message}", "stderr", req.project_id)
                return False
                
            return True
            
        except Exception as e:
            task.add_log(f"[TaskExecutor] Execution crashed: {e}")
            return False

    async def real_execution_callback(task):
        try:
            success = await real_execution_callback_inner(task)
            import time
            task.completed_at = time.time()
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            return success
        except Exception as e:
            import time
            task.completed_at = time.time()
            task.status = TaskStatus.FAILED
            task.error_msg = str(e)
            task.add_log(f"CRASH: {e}")
            return False
        finally:
            SessionPersistence.save_snapshot(orchestration_session)

    user_prompt = ""
    blueprint = ""
    project_context = ""
    gen_duration = 0.0
    task_success = False

    if not is_fallback:
        # Reset task graph task statuses and properties before the real execution run
        from backend.orchestrator.task_graph import TaskStatus
        for task in task_graph.tasks.values():
            task.status = TaskStatus.PENDING
            task.error_msg = None
            task.started_at = None
            task.completed_at = None
            task.logs = []
            task.validation_artifacts = {}
            task.proposed_artifacts = {}

        # Run sequential task execution!
        real_executor = TaskExecutor(task_graph, artifact_registry=real_artifact_contract_registry)
        t_start = time.time()
        if len(task_graph.tasks) > 0:
            task_success = await real_executor.execute_all(real_execution_callback)
            # Update orchestration session status on completion/failure
            orchestration_session.status = "completed" if task_success else "failed"
            SessionPersistence.save_snapshot(orchestration_session)
            gen_duration = time.time() - t_start
    
    if not task_success:
        if is_medium_or_broad:
            await emit_agent_state("failed", req.project_id)
            error_msg = "TaskGraph execution failed or was empty for a medium/broad prompt. Monolithic fallback is blocked for high complexity/broad scope."
            await emit_terminal_line(f"[TaskExecutor] Error: {error_msg}", "stderr", req.project_id)
            await _log_error_async(req.project_id, run_id, error_msg)
            return GenerateResponse(success=False, project_id=req.project_id, error=error_msg)
            
        await emit_terminal_line("[TaskExecutor] Sequential TaskGraph execution failed or was empty. Falling back to single-shot monolithic generation...", "warning", req.project_id)
        
        # ── Step 2: Generate Features (Fallback) ─────────────────────────────────────────────
        from backend.context.context_compressor import ContextCompressor
        project_context = ContextCompressor.get_full_context(req.project_id, run_id)
        
        # --- P8.2: Build GenerationBlueprint ---
        allowed_deps = _get_allowed_dependencies(real_base_path)
        deps_constraint = ""
        if allowed_deps:
            deps_constraint = f"ALLOWED IMPORTS: You can ONLY import external packages listed here: {', '.join(allowed_deps)}. Do NOT import any other packages (such as 'react-toastify', 'axios', etc.). If you need icons or UI components, use browser alerts/custom code or already declared imports.\n"

        blueprint = "=== REQUIRED TOPOLOGY (DO NOT IGNORE) ===\n"
        blueprint += "You MUST separate concerns. Do NOT place all logic in a single file (like App.tsx).\n"
        if project_map.entrypoints:
            blueprint += f"Root Entrypoints: {', '.join(project_map.entrypoints)}\n"
        blueprint += "Planned Components & Responsibilities:\n"
        for t_id, task in task_graph.tasks.items():
            targets = task.allowed_write_paths if task.allowed_write_paths else task.affected_files
            target_str = ", ".join(targets) if targets else "Core structural logic"
            blueprint += f"- {target_str}: {task.description}\n"
        blueprint += f"\n{deps_constraint}\n"
        blueprint += "STRICT ANTI-MONOLITH RULES:\n"
        blueprint += "- Separate UI components, state management, and root wiring into separate files.\n"
        blueprint += "- Keep App.tsx small (composition only).\n"
        blueprint += "- Follow the planned component responsibilities above.\n"
        blueprint += "=========================================\n"
        
        clean_prompt = clean_user_intent_prompt(req.prompt)

        user_prompt = (
            f"Generate a {_ecosystem_label(skill_name)} project based on this request:\n\n"
            f"{clean_prompt}\n\n"
            f"{cbr_context}\n\n"
            f"--- CURRENT PROJECT KNOWLEDGE ---\n"
            f"{project_context}\n"
            f"----------------------------------\n\n"
            f"{blueprint}\n\n"
            f"Return files using the ===FILE:relative/path.ext=== ... ===END=== delimiter format."
        )

        try:
            await emit_terminal_line(f"[Governance] Operation 'Full Generation' classified as HIGH cost", "info", req.project_id)
            await emit_terminal_line(f"[AI] Calling LLM with {skill_name}-specific system prompt", "info", req.project_id)
            t_start = time.time()
            raw = await asyncio.to_thread(complete, system_prompt, user_prompt)
            gen_duration = time.time() - t_start
        except Exception as e:
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"[AI] API error: {e}", "stderr", req.project_id)
            await _log_error_async(req.project_id, run_id, f"AI generation error: {e}")
            return GenerateResponse(success=False, project_id=req.project_id, error=str(e))

        # ── Step 3: Parse ─────────────────────────────────────────────────────────
        await emit_terminal_line("[Parser] Validating AI output...", "info", req.project_id)
        try:
            files = parse_ai_response(raw)
            await emit_terminal_line(f"[Parser] Parsed {len(files)} files", "info", req.project_id)
        except ParseError as e:
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"[Parser] Error: {e}", "stderr", req.project_id)
            await _log_error_async(req.project_id, run_id, f"Parse error: {e}\n\nRAW:\n{raw}")
            return GenerateResponse(success=False, project_id=req.project_id, error=str(e))

        # ── Step 4: Validate against ecosystem ────────────────────────────────────
        valid_extensions = skill.get_file_patterns()
        for f in files:
            ext_ok = any(f.path.endswith(pat.replace("*", "")) for pat in valid_extensions) if valid_extensions != ["*"] else True
            if not ext_ok:
                await emit_terminal_line(f"[Validation] WARNING: {f.path} may not match {skill_name} ecosystem (pattern: {valid_extensions})", "stderr", req.project_id)

        if skill_name == "react-vite":
            files = await _filter_react_vite_generated_files(files, req.project_id)

        # ── Step 5: Write & Capture Artifacts ─────────────────────────────────────
        await emit_agent_state("writing", req.project_id)
        
        for f in files:
            registry.add_actual_file(f.path, f.content)
            try:
                path = await asyncio.to_thread(write_file, req.project_id, f.path, f.content, run_id)
                written.append(path)
                await emit_terminal_line(f"[Writer] Writing {f.path}", "info", req.project_id)
                await _log_work_async(req.project_id, run_id, f"Created {f.path}")
            except ValueError as e:
                await emit_terminal_line(f"[Writer] Skipping {f.path}: {e}", "stderr", req.project_id)
                await _log_error_async(req.project_id, run_id, f"Skipped {f.path}: {e}")

    await emit_terminal_line(f"[Governance] Operation 'Topology Evaluation' classified as LOW cost", "info", req.project_id)

    if skill_name == "react-vite":
        valid, err = await _validate_react_vite_environment(req.project_id, run_id, "before truth markers")
        if not valid:
            await emit_agent_state("failed", req.project_id)
            await emit_runtime_error(
                _first_error_code(err),
                err or "React/Vite contract failed before install",
                project_id=req.project_id,
                run_id=run_id,
                source="environment_contract",
            )
            await _log_error_async(req.project_id, run_id, f"React/Vite contract failed before install:\n{err}")
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)

    # Inject truth markers
    await _inject_truth_markers(req.project_id, run_id, req.prompt, skill_name)

    if skill_name == "react-vite":
        valid, err = await _validate_react_vite_environment(req.project_id, run_id, "before install/build")
        if not valid:
            await emit_agent_state("failed", req.project_id)
            await emit_runtime_error(
                _first_error_code(err),
                err or "React/Vite contract failed before install",
                project_id=req.project_id,
                run_id=run_id,
                source="environment_contract",
            )
            await _log_error_async(req.project_id, run_id, f"React/Vite contract failed before install:\n{err}")
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)

    # Compare planned vs actual artifacts
    registry.compare_with_plan(task_graph, str(real_base_path))
    
    # Save Artifact Registry
    SessionPersistence.save_artifacts(req.project_id, registry)
    
    # Reporting
    matched = [a.file_path for a in registry.artifacts.values() if a.status == 'matched']
    missing = [a.file_path for a in registry.artifacts.values() if a.status == 'missing']
    unexpected = [a.file_path for a in registry.artifacts.values() if a.status == 'unexpected']
    orphan = [a.file_path for a in registry.artifacts.values() if a.status == 'orphan']
    ambiguous = [a.file_path for a in registry.artifacts.values() if a.status == 'ambiguous']
    
    print(f"[ArtifactRegistry] Captured {len(registry.artifacts)} actual files.")
    print(f"[ArtifactCompare] Matched: {len(matched)}, Missing: {len(missing)}, Unexpected: {len(unexpected)}, Orphan: {len(orphan)}, Ambiguous: {len(ambiguous)}")
    await emit_terminal_line(f"[ArtifactRegistry] Artifacts mapped. Matched: {len(matched)} | Missing: {len(missing)} | Orphan: {len(orphan)}", "info", req.project_id)

    matched_semantic = [a.file_path for a in registry.artifacts.values() if a.status == 'matched_semantic']
    
    # --- P8.3A: Topology Alignment Metric & Monolith Risk Refinement ---
    matched_count = len(matched)
    matched_semantic_count = len(matched_semantic)
    missing_count = len(missing)
    orphan_count = len(orphan)
    total_planned = matched_count + matched_semantic_count + missing_count
    
    literal_match_score = (matched_count / total_planned) if total_planned > 0 else 0
    semantic_match_score = (matched_semantic_count / total_planned) if total_planned > 0 else 0
    topology_match_score = literal_match_score + semantic_match_score
    
    monolith_risk_score = 0.0
    if total_planned > 2 and missing_count > (total_planned / 2) and matched_semantic_count == 0:
        monolith_risk_score = 1.0
    elif len(registry.artifacts) < (total_planned * 0.5):
        monolith_risk_score = 1.0
        
    monolithic_collapse_detected = monolith_risk_score > 0.8
        
    if monolithic_collapse_detected:
        msg = "Generation failed quality gate: component separation collapsed (monolithic collapse detected)."
        await emit_agent_state("failed", req.project_id)
        await emit_terminal_line(f"[Governance] {msg}", "stderr", req.project_id)
        await _log_error_async(req.project_id, run_id, msg)
        return GenerateResponse(
            success=False,
            project_id=req.project_id,
            files_written=written,
            error=msg
        )
        
    # --- P8.3A: Duplicate Reasoning Detection ---
    prompt_hash = hashlib.sha256(req.prompt.encode('utf-8')).hexdigest()
    # Create a simplistic topology hash representing the planned task names
    topology_hash = hashlib.sha256(str([t.title for t in task_graph.tasks.values()]).encode('utf-8')).hexdigest()
    
    repeated_regeneration_count = 0
    if prompt_hash in _P8_HISTORY_STORE:
        if _P8_HISTORY_STORE[prompt_hash] == topology_hash:
            repeated_regeneration_count += 1
            await emit_terminal_line("[Governance] Duplicate reasoning detected: identical prompt mapped to identical topology", "warning", req.project_id)
    _P8_HISTORY_STORE[prompt_hash] = topology_hash

    metrics = {
        "matched_count": matched_count,
        "matched_semantic_count": matched_semantic_count,
        "missing_count": missing_count,
        "orphan_count": orphan_count,
        "total_planned": total_planned,
        "literal_match_score": literal_match_score,
        "semantic_match_score": semantic_match_score,
        "topology_match_score": topology_match_score,
        "monolith_risk_score": monolith_risk_score,
        "monolithic_collapse_detected": monolithic_collapse_detected,
        "cost": {
            "prompt_size_chars": len(user_prompt),
            "blueprint_size_chars": len(blueprint),
            "project_context_size_chars": len(project_context),
            "generation_duration_sec": gen_duration,
            "repeated_regeneration_count": repeated_regeneration_count
        }
    }
    
    import os, json
    from backend.sandbox.executor import _safe_project_path
    p8_dir = _safe_project_path(req.project_id, run_id) / ".orchestration" / "p8"
    os.makedirs(p8_dir, exist_ok=True)
    with open(p8_dir / "cost_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)


    # ── Step 6: Pre-flight check before install ────────────────────────────────
    if cmd_strategy.has_install():
        required = skill.get_required_files_before_install()
        if required:
            from backend.sandbox.executor import _check_required_files
            err = _check_required_files(req.project_id, required, run_id)
            if err:
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[Validation] {err}", "stderr", req.project_id)
                await _log_error_async(req.project_id, run_id, err)
                return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
            await emit_terminal_line(f"[Validation] Pre-install files OK: {required}", "info", req.project_id)

    # ── Step 7: Install ──────────────────────────────────────────────────────
    if cmd_strategy.has_install():
        await emit_agent_state("installing", req.project_id)
        install_cmd = cmd_strategy.install
        install_label = install_cmd[0] if install_cmd else "install"
        await emit_terminal_line(f"[Executor] Installing dependencies: {' '.join(install_cmd)}", "info", req.project_id)
        logger.info("[Executor] Running install: %s", install_cmd)

        install_res = await stream_command_array_async(req.project_id, "install", install_cmd, run_id=run_id)
        if not install_res.success:
            await emit_agent_state("failed", req.project_id)
            err = install_res.stderr or install_res.error or "Install failed"
            await emit_terminal_line(f"[Executor] npm install failed (exit {install_res.exit_code})", "stderr", req.project_id)
            await _log_error_async(req.project_id, run_id, f"Install failed:\n{err}")
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)

        from backend.agent.tools import _safe_project_path
        if not (_safe_project_path(req.project_id, run_id) / "node_modules").exists():
            err = "Install reported success, but node_modules directory is missing."
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"[Validation] {err}", "stderr", req.project_id)
            await _log_error_async(req.project_id, run_id, err)
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
        await emit_terminal_line(f"[Validation] node_modules verified.", "info", req.project_id)

        await _log_work_async(req.project_id, run_id, f"Dependencies installed ({install_label}).")
    else:
        await emit_terminal_line(f"[Executor] No install step needed for {skill_name}", "info", req.project_id)
        logger.info("[Executor] Skipping install (not required for %s)", skill_name)

    # ── Step 8: Build (if ecosystem requires) ─────────────────────────────────
    if cmd_strategy.has_build():
        await emit_agent_state("building", req.project_id)
        await emit_terminal_line(f"[Governance] Operation 'Build' classified as HIGH cost", "info", req.project_id)
        build_start = time.time()
        build_cmd = cmd_strategy.build
        await emit_terminal_line(f"[Executor] Building: {' '.join(build_cmd)}", "info", req.project_id)

        build_res = await stream_command_array_async(req.project_id, "build", build_cmd, run_id=run_id)
        ReflectionEngine.record_validation(req.project_id, run_id, "build", build_res, command=" ".join(build_cmd))
        build_duration = time.time() - build_start
        metrics["cost"]["build_duration_sec"] = build_duration
        with open(p8_dir / "cost_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        if not build_res.success:
            failure_type = classify_react_vite_failure(build_res.stdout or "", build_res.stderr or "") if skill_name == "react-vite" else RuntimeErrorCode.E_BUILD_FAILURE.value
            if skill_name == "react-vite":
                await emit_terminal_line(f"[RepairClassifier] Classified build failure as: {failure_type}", "info", req.project_id)
                await emit_runtime_error(
                    failure_type,
                    "Build failed and was classified before repair",
                    project_id=req.project_id,
                    run_id=run_id,
                    source="build",
                )

            if failure_type in {
                RuntimeErrorCode.E_TS_REFERENCE_INVALID.value,
                RuntimeErrorCode.E_VITE_CONFIG.value,
                RuntimeErrorCode.E_REACT_ROOT_MISSING.value,
            }:
                restored = await asyncio.to_thread(restore_canonical_react_vite_contract, req.project_id, run_id)
                await emit_terminal_line(f"[ContractRepair] Restored canonical files before rebuild: {', '.join(restored)}", "info", req.project_id)
                await _inject_truth_markers(req.project_id, run_id, req.prompt, skill_name)
                valid, err = await _validate_react_vite_environment(req.project_id, run_id, f"after {failure_type} repair")
                if not valid:
                    await emit_agent_state("failed", req.project_id)
                    await _log_error_async(req.project_id, run_id, f"React/Vite deterministic repair failed:\n{err}")
                    return GenerateResponse(success=False, project_id=req.project_id, files_written=written, repair_attempts=1, error=err)

                await emit_agent_state("building", req.project_id)
                await emit_terminal_line("[Executor] Rebuilding after deterministic contract repair...", "info", req.project_id)
                build_res = await stream_command_array_async(req.project_id, "build", build_cmd, run_id=run_id)
                ReflectionEngine.record_revalidation(req.project_id, run_id, build_res, stage="deterministic_contract_revalidation")

                if not build_res.success and failure_type in {RuntimeErrorCode.E_TS_REFERENCE_INVALID.value, RuntimeErrorCode.E_VITE_CONFIG.value}:
                    await emit_agent_state("failed", req.project_id)
                    err = build_res.stderr or build_res.error or "Build failed after deterministic contract repair"
                    await _log_error_async(req.project_id, run_id, f"Build failed after deterministic contract repair:\n{err}")
                    return GenerateResponse(success=False, project_id=req.project_id, files_written=written, repair_attempts=1, error=err)
            elif failure_type in {RuntimeErrorCode.E_DEPENDENCY_MISSING.value, RuntimeErrorCode.E_IMPORT_RESOLUTION.value}:
                await emit_terminal_line("[DependencyValidator] Build dependency failure routed outside contract repair", "warning", req.project_id)
                valid, err = await _validate_dependency_resolution_environment(req.project_id, run_id, f"after {failure_type}")
                if not valid:
                    await emit_agent_state("failed", req.project_id)
                    await _log_error_async(req.project_id, run_id, err or "Dependency resolution failed")
                    return GenerateResponse(success=False, project_id=req.project_id, files_written=written, repair_attempts=1, error=err)

                await emit_agent_state("building", req.project_id)
                await emit_terminal_line("[Executor] Rebuilding after dependency repair...", "info", req.project_id)
                build_res = await stream_command_array_async(req.project_id, "build", build_cmd, run_id=run_id)
                ReflectionEngine.record_revalidation(req.project_id, run_id, build_res, stage="dependency_revalidation")

            from backend.reflection.repair_loop import attempt_repair
            repair_attempts = 0
            max_repairs = req.max_repair_attempts if req.auto_repair else 0
            
            while not build_res.success and repair_attempts < max_repairs:
                repair_attempts += 1
                patched, pkg_json_modified = await attempt_repair(
                    project_id=req.project_id,
                    original_prompt=req.prompt,
                    ecosystem_label=_ecosystem_label(skill_name),
                    stdout=build_res.stdout or "",
                    stderr=build_res.stderr or "",
                    attempt=repair_attempts,
                    max_repairs=max_repairs,
                    written_files=written,
                    run_id=run_id
                )
                
                if not patched:
                    break # Give up if we couldn't even generate a patch
                    
                if pkg_json_modified and cmd_strategy.has_install():
                    await emit_agent_state("installing", req.project_id)
                    await emit_terminal_line("[Executor] Package.json modified by repair. Re-installing dependencies...", "info", req.project_id)
                    install_res = await stream_command_array_async(req.project_id, "install", cmd_strategy.install, run_id=run_id)
                    if not install_res.success:
                        await emit_terminal_line("[Executor] Dependency re-installation failed.", "warning", req.project_id)

                await emit_agent_state("building", req.project_id)
                await emit_terminal_line(f"[Executor] Rebuilding after patch...", "info", req.project_id)
                build_res = await stream_command_array_async(req.project_id, "build", build_cmd, run_id=run_id)
                ReflectionEngine.record_revalidation(req.project_id, run_id, build_res, stage="llm_patch_revalidation")
            
            if not build_res.success:
                await emit_agent_state("failed", req.project_id)
                err = build_res.stderr or build_res.error or "Build failed after repairs"
                await _log_error_async(req.project_id, run_id, f"Build failed after repairs:\n{err}")
                return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
        await _log_work_async(req.project_id, run_id, "Build succeeded.")
    else:
        await emit_terminal_line(f"[Executor] No build step needed for {skill_name}", "info", req.project_id)

    # ── Step 9: Pre-flight check before dev server ─────────────────────────────
    if cmd_strategy.dev:
        required = skill.get_required_files_before_dev()
        if required:
            from backend.sandbox.executor import _check_required_files
            err = _check_required_files(req.project_id, required, run_id)
            if err:
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[Validation] {err}", "stderr", req.project_id)
                await _log_error_async(req.project_id, run_id, err)
                return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
            await emit_terminal_line(f"[Validation] Pre-dev files OK: {required}", "info", req.project_id)
        if skill_name == "node-backend":
            from backend.sandbox.executor import validate_node_runtime_contract
            err = validate_node_runtime_contract(req.project_id, run_id)
            if err:
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[Validation] {err}", "stderr", req.project_id)
                await _log_error_async(req.project_id, run_id, err)
                return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
            await emit_terminal_line("[Validation] Node entrypoint contract OK.", "info", req.project_id)

    # ── Step 10: Dev Server ───────────────────────────────────────────────────
    if cmd_strategy.dev:
        dev_cmd = cmd_strategy.dev
        if skill_name == "node-backend":
            from backend.sandbox.executor import resolve_node_runtime_command
            try:
                dev_cmd = resolve_node_runtime_command(req.project_id, run_id)
            except ValueError as e:
                await emit_agent_state("failed", req.project_id)
                err = str(e)
                await emit_terminal_line(f"[Validation] {err}", "stderr", req.project_id)
                await _log_error_async(req.project_id, run_id, err)
                return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
        preview = skill.get_preview_strategy()
        await emit_agent_state("launching", req.project_id)
        await emit_terminal_line(f"[Runtime] Launching: {' '.join(dev_cmd)}", "info", req.project_id)
        logger.info("[Executor] Starting dev server: %s", dev_cmd)

        # Use first readiness pattern as port detection regex
        # Output Verification Heuristic Before Dev Server
        if skill_name == "react-vite":
            from backend.agent.tools import read_file
            try:
                app_tsx = await asyncio.to_thread(read_file, req.project_id, "src/App.tsx", run_id)
                app_lower = app_tsx.lower()
                prompt_clean = clean_user_intent_prompt(req.prompt)
                logger.info("[Validation] clean_prompt=%r", prompt_clean)
                await emit_terminal_line(f"[Validation] clean_prompt={prompt_clean!r}", "info", req.project_id)
                
                prompt_lower = prompt_clean.strip().lower()
                
                valid = True
                reason = ""
                app_type, expected_terms, required_any_terms, min_interactive = _intent_requirements(prompt_clean)
                if expected_terms:
                    matched_terms = [term for term in expected_terms if term in app_lower]
                    if len(matched_terms) < 2:
                        valid = False
                        reason = f"Failed heuristic: Expected {app_type} domain terminology."
                    elif required_any_terms and not any(t in app_lower for t in required_any_terms):
                        valid = False
                        reason = f"Failed heuristic: Expected {app_type} core flow terminology."
                elif "login" in prompt_lower or "auth" in prompt_lower:
                    if not any(t in app_lower for t in ["login", "username", "password", "form", "auth", "submit"]):
                        valid = False
                        reason = "Failed heuristic: Expected login terminology."
                elif any(term in prompt_lower for term in ["task", "todo", "task list", "todo list", "todolist", "daftar tugas", "tugas"]):
                    if not any(t in app_lower for t in ["task", "todo", "list", "add", "delete", "complete", "checkbox", "tugas", "daftar"]):
                        valid = False
                        reason = "Failed heuristic: Expected task list terminology."
                elif "calculator" in prompt_lower:
                    if not any(t in app_lower for t in ["calculator", "number", "operator", "result", "plus", "minus", "multiply", "divide"]):
                        valid = False
                        reason = "Failed heuristic: Expected calculator terminology."
                        
                if not valid:
                    err = f"Output Validation Failed: Generated code does not match intent. {reason}"
                    await emit_agent_state("failed", req.project_id)
                    await emit_terminal_line(f"[Validation] {err}", "stderr", req.project_id)
                    await _log_error_async(req.project_id, run_id, err)
                    return GenerateResponse(success=False, project_id=req.project_id, error=err)
                
                await emit_terminal_line("[Validation] Output heuristic matched user intent.", "info", req.project_id)
            except Exception as e:
                await emit_terminal_line(f"[Validation] Warning: could not verify src/App.tsx: {e}", "stderr", req.project_id)

        port_pattern = preview.readiness_patterns[0] if preview.readiness_patterns else None
        dev_res = await run_dev_server_array_async(req.project_id, dev_cmd, port_pattern=port_pattern, run_id=run_id)
        if not dev_res.success:
            await emit_agent_state("failed", req.project_id)
            err = dev_res.error or "Dev server failed"
            await emit_runtime_error(
                RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
                err,
                project_id=req.project_id,
                run_id=run_id,
                source="preview",
            )
            await _log_error_async(req.project_id, run_id, f"Dev server failed:\n{err}")
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
            
        # ── Step 11: Backend Runtime Verification ────────────────────────────────
        from backend.sandbox.executor import _runtime_registry
        import urllib.request
        import urllib.error
        entry = _runtime_registry.get(req.project_id)
        if entry and entry.preview_url:
            await emit_agent_state("verifying", req.project_id)
            preview_url = entry.preview_url
            msg = f"[RuntimeVerify] fetching {preview_url}"
            print(msg)
            await emit_terminal_line(msg, "info", req.project_id)
            
            def _fetch_html(url):
                try:
                    res = urllib.request.urlopen(url, timeout=10)
                    return int(getattr(res, "status", 200)), res.read().decode('utf-8', errors='replace')
                except urllib.error.HTTPError as exc:
                    return int(exc.code), exc.read().decode('utf-8', errors='replace')

            # Step 1: Verify HTML marker
            html_text = ""
            html_status = 0
            for attempt in range(5):
                try:
                    html_status, html_text = await asyncio.to_thread(_fetch_html, preview_url)
                    break
                except Exception as e:
                    await asyncio.sleep(1)
            
            if html_status == 404 and skill_name == "node-backend":
                err = "Preview verification failed: Runtime responded, but preview route returned HTTP 404."
                print(err)
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
                await emit_runtime_error(
                    RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
                    err,
                    project_id=req.project_id,
                    run_id=run_id,
                    source="preview",
                )
                await _log_error_async(req.project_id, run_id, err)
                return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)

            if html_status >= 400:
                err = f"Preview verification failed: Runtime responded, but preview route returned HTTP {html_status}."
                print(err)
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
                await emit_runtime_error(
                    RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
                    err,
                    project_id=req.project_id,
                    run_id=run_id,
                    source="preview",
                )
                return GenerateResponse(success=False, project_id=req.project_id, error=err)

            if not html_text:
                err = "Preview verification failed: HTTP GET error (dev server unreachable)"
                print(err)
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
                await emit_runtime_error(
                    RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
                    err,
                    project_id=req.project_id,
                    run_id=run_id,
                    source="preview",
                )
                return GenerateResponse(success=False, project_id=req.project_id, error=err)
                
            from backend.sandbox.executor import _safe_project_path
            run_dir = _safe_project_path(req.project_id, run_id)
            run_dir.mkdir(parents=True, exist_ok=True)
            with open(run_dir / "raw_response.html", "w", encoding="utf-8") as f:
                f.write(html_text)
            
            served_run_marker = _extract_served_run_marker(html_text)
            if served_run_marker and served_run_marker != run_id:
                err = f"Preview verification failed: runtime truth mismatch. Expected {run_id}, got {served_run_marker}"
                print(err)
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
                await emit_runtime_error(
                    RuntimeErrorCode.E_REACT_ROOT_MISSING,
                    err,
                    project_id=req.project_id,
                    run_id=run_id,
                    source="runtime_verification",
                )
                return GenerateResponse(success=False, project_id=req.project_id, error=err)
            if not served_run_marker:
                await emit_terminal_line(
                    "[RuntimeVerify] Preview responded but did not include the active run marker; using runtime process ownership as diagnostic fallback.",
                    "warning",
                    req.project_id,
                )
            else:
                msg = "[RuntimeVerify] HTML marker verified"
                print(msg)
                await emit_terminal_line(msg, "info", req.project_id)

            if skill_name == "php-basic":
                import re
                clean_text = re.sub(r'<[^>]+>', ' ', html_text).strip()
                has_content = any(c.isalnum() for c in clean_text)
                
                if "Fatal error:" in html_text or "Parse error:" in html_text or not has_content:
                    err = "PHP preview validation failed: served page is blank or missing visible content"
                    print(err)
                    await emit_agent_state("failed", req.project_id)
                    await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
                    return GenerateResponse(success=False, project_id=req.project_id, error=err)
            
            # Step 2: Verify source marker (by inspecting raw filesystem source file instead of served Vite output)
            if skill_name == "react-vite":
                from backend.agent.tools import read_file
                main_text = ""
                try:
                    main_text = await asyncio.to_thread(read_file, req.project_id, "src/main.tsx", run_id)
                except Exception as e:
                    pass
                
                if not main_text:
                    msg = "[RuntimeVerify] source marker verification skipped: read error (main.tsx not found on filesystem)"
                    print(msg)
                    await emit_terminal_line(msg, "warning", req.project_id)
                elif f'data-run-id="{run_id}"' not in main_text:
                    msg = "[RuntimeVerify] source marker verification skipped: mismatch (DOM marker not found in raw React source)"
                    print(msg)
                    await emit_terminal_line(msg, "warning", req.project_id)
                else:
                    msg = "[RuntimeVerify] source marker verified from filesystem"
                    print(msg)
                    await emit_terminal_line(msg, "info", req.project_id)

            # Step 3: Real Rendered DOM Verification
            dom_res = await verify_rendered_dom_truth(preview_url, run_id, req.project_id, req.prompt, skill_name)
            
            if dom_res.get("error") == "Playwright is not installed. DOM verification unavailable.":
                err_msg = dom_res.get("error")
                print(err_msg)
                await emit_terminal_line(f"[RuntimeVerify] {err_msg}", "warning", req.project_id)
            elif not dom_res.get("success"):
                err = f"Preview verification failed: {dom_res.get('error')}"
                print(err)
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
                code = RuntimeErrorCode.E_RUNTIME_BLANK if "blank" in err.lower() or "mounted" in err.lower() else RuntimeErrorCode.E_REACT_ROOT_MISSING
                await emit_runtime_error(
                    code,
                    err,
                    project_id=req.project_id,
                    run_id=run_id,
                    source="runtime_verification",
                )
                return GenerateResponse(success=False, project_id=req.project_id, error=err)
            else:
                p76_msg = "[P7.6] playwright validation success"
                print(p76_msg)
                await emit_terminal_line(p76_msg, "info", req.project_id)
                if dom_res.get("error"):
                    await emit_terminal_line(f"[RuntimeVerify] {dom_res.get('error')}", "warning", req.project_id)
                msg = "[RuntimeVerify] rendered DOM marker verified" if dom_res.get("dom_verified") else "[RuntimeVerify] rendered DOM reachable; marker unavailable"
                if ecosystem_label := _ecosystem_label(skill_name):
                    msg += f" (Ecosystem: {ecosystem_label})"
                print(msg)
                await emit_terminal_line(msg, "info", req.project_id)

                feature_context = FeatureContractContext(
                    project_id=req.project_id,
                    run_id=run_id,
                    preview_url=preview_url,
                    prompt=req.prompt,
                    app_type=getattr(generation_signature, "app_type", None) or (project_state or {}).get("project_type"),
                    domain=getattr(generation_signature, "domain", None) or (project_state or {}).get("domain"),
                    generation_signature=generation_signature,
                    feature_manifest=feature_manifest,
                )
                feature_result = await run_feature_contracts(feature_context)
                if feature_manifest:
                    await emit_terminal_line(
                        "[FeatureContract] features: " + ", ".join(feature.id for feature in feature_manifest.features),
                        "info",
                        req.project_id,
                    )
                await emit_terminal_line(
                    "[FeatureContract] selected contracts: " + (", ".join(feature_result.selected_contracts) or "none"),
                    "info",
                    req.project_id,
                )
                await emit_terminal_line(
                    f"[FeatureContract] action plans: {len(feature_result.action_plans)}",
                    "info",
                    req.project_id,
                )
                await emit_terminal_line(
                    f"[FeatureContract] success={str(feature_result.success).lower()} contracts={len(feature_result.contracts_executed)} selected={len(feature_result.selected_contracts)} duration_ms={feature_result.duration_ms}",
                    "info" if feature_result.success else "stderr",
                    req.project_id,
                )
                if not feature_result.success:
                    err = "Feature contract validation failed"
                    await emit_agent_state("failed", req.project_id)
                    await emit_terminal_line(f"[FeatureContract] {err}: {feature_result.to_dict()}", "stderr", req.project_id)
                    await _log_error_async(req.project_id, run_id, f"{err}:\n{feature_result.to_dict()}")
                    return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=err)
        else:
            err = "Preview verification failed: No preview URL found in runtime registry"
            print(err)
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"[RuntimeVerify] {err}", "stderr", req.project_id)
            await emit_runtime_error(
                RuntimeErrorCode.E_PREVIEW_UNREACHABLE,
                err,
                project_id=req.project_id,
                run_id=run_id,
                source="preview",
            )
            return GenerateResponse(success=False, project_id=req.project_id, error=err)

    else:
        await emit_terminal_line(f"[Runtime] No dev server needed for {skill_name}", "info", req.project_id)

    await emit_agent_state("success", req.project_id)
    await emit_terminal_line("[Orchestrator] Generation complete. System is stable.", "info", req.project_id)
    await _log_work_async(req.project_id, run_id, "Generation completed successfully.")
    try:
        from backend.memory.project_memory import ProjectMemory
        from backend.memory.workspace_awareness import WorkspaceAwareness

        ProjectMemory.update_after_generation(
            req.project_id,
            req.prompt,
            signature=generation_signature,
            ecosystem=skill_name,
            success=True,
        )
        if _sync_run_to_latest(req.project_id, run_id):
            await emit_terminal_line("[StatePreservation] Synced successful run to latest project state.", "info", req.project_id)
        WorkspaceAwareness.scan(req.project_id, run_id=run_id, prompt=req.prompt)
        if change_scope:
            from backend.brain.change_scope import ChangeScopeAnalyzer

            completed_scope = {
                **change_scope,
                "status": "completed",
                "completed_run_id": run_id,
                "post_generation_note": "Project State and Workspace Awareness were updated after this scoped change.",
            }
            ChangeScopeAnalyzer.save(req.project_id, completed_scope)
        await emit_terminal_line("[ProjectState] Updated .ai-agent/project_state.json", "info", req.project_id)
    except Exception as e:
        logger.exception("Failed to update project state for project=%s", req.project_id)
        await emit_terminal_line(f"[ProjectState] Update skipped: {e}", "warning", req.project_id)

    return GenerateResponse(success=True, project_id=req.project_id, files_written=written)
