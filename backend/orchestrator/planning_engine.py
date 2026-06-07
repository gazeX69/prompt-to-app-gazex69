import json
import asyncio
import logging
from typing import Any
from backend.brain.domain_contract_registry import DomainContractError, load_contract
from backend.brain.plan_signature import build_plan_signature
from backend.brain.prompt_cleaning import clean_user_intent_prompt
from backend.services.ai_service import complete
from backend.orchestrator.project_mapper import ProjectMap
from backend.orchestrator.task_graph import ExecutionTask, TaskGraph, ValidationContract, PatchOperation

logger = logging.getLogger(__name__)


class PlanningFailure(RuntimeError):
    pass


class PlanningEngine:
    """
    Ingests ProjectMap and User Intent.
    Generates deterministic ExecutionTask scopes without directly executing.
    """
    @staticmethod
    def _deterministic_plan(prompt: str) -> TaskGraph | None:
        try:
            clean_prompt = clean_user_intent_prompt(prompt)
            signature = build_plan_signature(clean_prompt)
            if signature.app_type == "unknown_domain":
                return None
            contract = load_contract(signature.app_type)
        except (DomainContractError, Exception):
            return None

        def make_task(
            template: dict[str, Any],
        ) -> ExecutionTask:
            affected_files = [str(path).lstrip("/\\") for path in template.get("affected_files") or []]
            return ExecutionTask(
                id=str(template.get("id") or ""),
                title=str(template.get("title") or ""),
                description=str(template.get("description") or ""),
                affected_files=affected_files,
                allowed_write_paths=affected_files,
                forbidden_paths=["package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "index.html", "src/main.tsx"],
                dependencies=[str(dep) for dep in template.get("dependencies") or []],
                produces_artifacts=[str(item) for item in template.get("produces_artifacts") or template.get("produces") or []],
                requires_artifacts=[str(item) for item in template.get("requires_artifacts") or template.get("requires") or []],
                validation_contract=ValidationContract(
                    success_criteria=[str(item) for item in template.get("success_criteria") or ["feature renders", "state updates correctly"]],
                    runtime_proof_required=True,
                    artifact_proof_required=True,
                    verification_method="grep",
                ),
            )

        task_templates = contract.get("task_templates") or []
        if not task_templates:
            return None

        graph = TaskGraph()
        for template in task_templates:
            task = make_task(template)
            if task.id:
                graph.add_task(task)
        if not graph.tasks:
            return None
        return graph

    @staticmethod
    async def create_plan(prompt: str, ecosystem_label: str, project_map: ProjectMap) -> TaskGraph:
        clean_prompt = clean_user_intent_prompt(prompt)
        signature = build_plan_signature(clean_prompt)
        logger.info(
            "[Planning] intent=%s app_type=%s domain=%s clean_prompt=%r",
            signature.intent,
            signature.app_type,
            signature.domain,
            clean_prompt,
        )

        llm_reason = "unknown_domain"
        if signature.app_type != "unknown_domain":
            deterministic = PlanningEngine._deterministic_plan(clean_prompt)
            if deterministic is not None and len(deterministic.tasks) > 0:
                logger.info(
                    "[Planning] contract_deterministic_plan_used app_type=%s domain=%s tasks=%s",
                    signature.app_type,
                    signature.domain,
                    len(deterministic.tasks),
                )
                return deterministic
            llm_reason = "deterministic_plan_unavailable"

        logger.info(
            "[Planning] llm_planner_used app_type=%s domain=%s reason=%s",
            signature.app_type,
            signature.domain,
            llm_reason,
        )

        system_prompt = (
            "You are an AI Orchestration Planner.\n"
            "Your job is to break the user's intent into discrete, deterministic ExecutionTasks.\n"
            "Rules:\n"
            "- Do NOT generate code.\n"
            "- Do NOT attempt to fix everything. Scope strictly to the request.\n"
            "- Return a RAW JSON array of task objects (no markdown, no backticks).\n"
            "- Each task object must have: id, title, description, dependencies, affected_files, allowed_write_paths, forbidden_paths, success_criteria, patches.\n"
            "- For allowed_write_paths, define strictly what this task is allowed to mutate.\n"
            "- For forbidden_paths, explicitly list critical files (e.g. package.json, vite.config.ts) that this task must NOT touch.\n"
            "- For `patches`, it MUST be an array of objects. Each object must have: `operation_type` (e.g., 'insert_import', 'append_component', 'inject_hook', 'create_component', 'extend_route', 'modify_props', 'append_style_block', 'extend_provider'), `target_file`, `target_symbol` (optional), `insertion_strategy` (e.g., 'top', 'bottom', 'before_symbol', 'after_symbol', 'replace_symbol'), `expected_side_effects` (array of strings), `dependency_requirements` (array of strings).\n"
            "- Patch operations must be SMALL and LOCAL. Avoid rewrite_file, replace_component_tree, regenerate_module.\n"
            "- Provide clear locality reasoning in `expected_side_effects` or description (e.g. imports belong at top, hooks belong inside component scope, routes belong inside router).\n"
            f"- The ecosystem is {ecosystem_label}.\n"
        )
        
        user_prompt = (
            f"Intent: {clean_prompt}\n\n"
            f"--- PROJECT ARCHITECTURE ---\n"
            f"Ecosystem: {project_map.ecosystem}\n"
            f"Entrypoints: {project_map.entrypoints}\n"
            f"Frameworks: {project_map.frameworks}\n"
            f"Dependencies: {list(project_map.dependencies.keys())}\n"
            f"Modules: {project_map.modules}\n"
            f"----------------------------\n\n"
            "Generate the JSON array of tasks."
        )

        try:
            raw_response = await asyncio.to_thread(complete, system_prompt, user_prompt)
            import re
            
            # Clean JSON response from markdown blocks if present
            cleaned_response = raw_response.strip()
            if cleaned_response.startswith("```"):
                # Strip markdown fence
                lines = cleaned_response.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_response = "\n".join(lines).strip()
            
            # Helper to parse with trailing comma cleaning
            def parse_resilient(s: str):
                s = re.sub(r',\s*\}', '}', s)
                s = re.sub(r',\s*\]', ']', s)
                return json.loads(s)
                
            task_list = None
            # 1. Search for outer brackets [ ... ]
            json_match = re.search(r'\[\s*\{.*\}\s*\]', cleaned_response, flags=re.DOTALL)
            if not json_match:
                json_match = re.search(r'\[.*\]', cleaned_response, flags=re.DOTALL)
                
            if json_match:
                try:
                    task_list = parse_resilient(json_match.group(0))
                except Exception:
                    pass
                    
            # 2. If bracket search failed or wasn't a list, try object search (first '{' and last '}')
            if task_list is None:
                start_obj = cleaned_response.find('{')
                end_obj = cleaned_response.rfind('}')
                if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                    try:
                        obj_data = parse_resilient(cleaned_response[start_obj:end_obj+1])
                        if isinstance(obj_data, dict):
                            # Try to find list inside nested fields (e.g. {"tasks": [...]})
                            for k, v in obj_data.items():
                                if isinstance(v, list):
                                    task_list = v
                                    break
                    except Exception:
                        pass
                        
            if task_list is None or not isinstance(task_list, list):
                raise ValueError("Could not extract a valid JSON array of tasks from the planner output.")
            
            graph = TaskGraph()
            for t_data in task_list:
                val_contract = ValidationContract(
                    success_criteria=t_data.get("success_criteria", []),
                    runtime_proof_required=True,
                    artifact_proof_required=False,
                    verification_method="llm"
                )
                allowed_paths = [p.lstrip("/\\") for p in t_data.get("allowed_write_paths", [])]
                raw_forbidden = [p.lstrip("/\\") for p in t_data.get("forbidden_paths", [])]
                forbidden_paths = [fp for fp in raw_forbidden if fp not in allowed_paths]
                
                task = ExecutionTask(
                    id=t_data.get("id"),
                    title=t_data.get("title", ""),
                    description=t_data.get("description", ""),
                    affected_files=[p.lstrip("/\\") for p in t_data.get("affected_files", [])],
                    allowed_write_paths=allowed_paths,
                    forbidden_paths=forbidden_paths,
                    dependencies=t_data.get("dependencies", []),
                    produces_artifacts=[str(item) for item in t_data.get("produces_artifacts", [])],
                    requires_artifacts=[str(item) for item in t_data.get("requires_artifacts", [])],
                    validation_contract=val_contract
                )
                
                # P8.4A: Patch synthesis
                for p_data in t_data.get("patches", []):
                    patch = PatchOperation(
                        operation_type=p_data.get("operation_type", "unknown"),
                        target_file=p_data.get("target_file", "").lstrip("/\\"),
                        target_symbol=p_data.get("target_symbol"),
                        insertion_strategy=p_data.get("insertion_strategy", "append"),
                        expected_side_effects=p_data.get("expected_side_effects", []),
                        dependency_requirements=p_data.get("dependency_requirements", [])
                    )
                    task.patches.append(patch)
                    
                graph.add_task(task)
            
            return graph
            
        except Exception as e:
            deterministic = PlanningEngine._deterministic_plan(clean_prompt)
            if deterministic is not None:
                logger.warning(
                    "[Planning] deterministic_fallback_used app_type=%s domain=%s reason=%s",
                    signature.app_type,
                    signature.domain,
                    e,
                )
                return deterministic

            if signature.app_type == "hello_world" and "hello world" in clean_prompt.lower():
                logger.warning("[Planning] hello_world_simple_fallback_used reason=%s", e)
                graph = TaskGraph()
                graph.add_task(ExecutionTask(
                    id="hello_world_fallback",
                    title="Render Hello World",
                    description=f"Planner failed to parse JSON: {e}. Generating explicit hello world only.",
                    affected_files=["src/App.tsx"],
                    allowed_write_paths=["src/App.tsx"],
                    forbidden_paths=["package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "index.html", "src/main.tsx"],
                    validation_contract=ValidationContract(success_criteria=["hello world renders"]),
                ))
                return graph

            logger.error(
                "[Planning] monolithic_fallback_blocked intent=%s app_type=%s domain=%s clean_prompt=%r reason=%s",
                signature.intent,
                signature.app_type,
                signature.domain,
                clean_prompt,
                e,
            )
            raise PlanningFailure(
                f"Planner failed to produce valid JSON for {signature.app_type}; deterministic fallback unavailable. "
                "Unsafe monolithic fallback is blocked."
            ) from e
