import json
import asyncio
from backend.services.ai_service import complete
from backend.orchestrator.project_mapper import ProjectMap
from backend.orchestrator.task_graph import ExecutionTask, TaskGraph, ValidationContract, PatchOperation

class PlanningEngine:
    """
    Ingests ProjectMap and User Intent.
    Generates deterministic ExecutionTask scopes without directly executing.
    """
    @staticmethod
    async def create_plan(prompt: str, ecosystem_label: str, project_map: ProjectMap) -> TaskGraph:
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
            f"Intent: {prompt}\n\n"
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
            # Clean up the raw response in case it contains markdown formatting
            raw_response = raw_response.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            if raw_response.startswith("```"):
                raw_response = raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
                
            task_list = json.loads(raw_response.strip())
            
            graph = TaskGraph()
            for t_data in task_list:
                val_contract = ValidationContract(
                    success_criteria=t_data.get("success_criteria", []),
                    runtime_proof_required=True,
                    artifact_proof_required=False,
                    verification_method="llm"
                )
                task = ExecutionTask(
                    id=t_data.get("id"),
                    title=t_data.get("title", ""),
                    description=t_data.get("description", ""),
                    affected_files=t_data.get("affected_files", []),
                    allowed_write_paths=t_data.get("allowed_write_paths", []),
                    forbidden_paths=t_data.get("forbidden_paths", []),
                    dependencies=t_data.get("dependencies", []),
                    validation_contract=val_contract
                )
                
                # P8.4A: Patch synthesis
                for p_data in t_data.get("patches", []):
                    patch = PatchOperation(
                        operation_type=p_data.get("operation_type", "unknown"),
                        target_file=p_data.get("target_file", ""),
                        target_symbol=p_data.get("target_symbol"),
                        insertion_strategy=p_data.get("insertion_strategy", "append"),
                        expected_side_effects=p_data.get("expected_side_effects", []),
                        dependency_requirements=p_data.get("dependency_requirements", [])
                    )
                    task.patches.append(patch)
                    
                graph.add_task(task)
            
            return graph
            
        except Exception as e:
            # Fallback task if planner fails to respond with valid JSON
            graph = TaskGraph()
            task = ExecutionTask(
                id="fallback_task",
                title="Fallback Monolithic Generation",
                description=f"Planner failed to parse JSON: {e}. Executing standard fallback generation.",
                validation_contract=ValidationContract(success_criteria=["fallback_success"])
            )
            graph.add_task(task)
            return graph
