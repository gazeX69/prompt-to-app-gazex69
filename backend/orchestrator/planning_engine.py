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
    def _deterministic_plan(prompt: str) -> TaskGraph | None:
        try:
            from backend.brain.plan_signature import build_plan_signature

            signature = build_plan_signature(prompt)
        except Exception:
            return None

        def make_task(
            task_id: str,
            title: str,
            description: str,
            affected_files: list[str],
            dependencies: list[str] | None = None,
            criteria: list[str] | None = None,
        ) -> ExecutionTask:
            return ExecutionTask(
                id=task_id,
                title=title,
                description=description,
                affected_files=affected_files,
                allowed_write_paths=affected_files,
                forbidden_paths=["package.json", "vite.config.ts", "tsconfig.json", "tsconfig.app.json", "tsconfig.node.json", "index.html", "src/main.tsx"],
                dependencies=dependencies or [],
                validation_contract=ValidationContract(
                    success_criteria=criteria or ["feature renders", "state updates correctly"],
                    runtime_proof_required=True,
                    artifact_proof_required=True,
                    verification_method="grep",
                ),
            )

        recipes = {
            "marketplace": [
                make_task(
                    "types_and_seed_data",
                    "Define marketplace data model",
                    "Create Product, CartItem, Order, and checkout-related TypeScript types plus seeded products.",
                    ["src/types.ts", "src/data/seedProducts.ts"],
                    criteria=["Product type exists", "seed products exist"],
                ),
                make_task(
                    "marketplace_store",
                    "Create marketplace state store",
                    "Implement localStorage-backed product, cart, quantity, checkout, and admin CRUD state helpers.",
                    ["src/hooks/useMarketplaceStore.ts"],
                    ["types_and_seed_data"],
                    ["cart state exists", "localStorage persistence exists"],
                ),
                make_task(
                    "marketplace_components",
                    "Build marketplace UI components",
                    "Create product browsing, cart, checkout simulation, and admin product management components.",
                    ["src/components/ProductCatalog.tsx", "src/components/CartPanel.tsx", "src/components/AdminPanel.tsx"],
                    ["marketplace_store"],
                    ["product list renders", "cart controls render", "admin CRUD renders"],
                ),
                make_task(
                    "compose_marketplace_app",
                    "Compose marketplace app shell",
                    "Wire the marketplace components into src/App.tsx with responsive navigation and visible MVP flows.",
                    ["src/App.tsx"],
                    ["marketplace_components"],
                    ["marketplace app renders"],
                ),
            ],
            "inventory": [
                make_task("inventory_types", "Define inventory model", "Create item and stock movement types plus seed inventory.", ["src/types.ts", "src/data/seedInventory.ts"]),
                make_task("inventory_store", "Create inventory state", "Implement localStorage-backed item CRUD, stock adjustment, and low-stock helpers.", ["src/hooks/useInventoryStore.ts"], ["inventory_types"]),
                make_task("inventory_components", "Build inventory screens", "Create item table, item form, stock summary, and low-stock indicators.", ["src/components/InventoryTable.tsx", "src/components/InventoryForm.tsx", "src/components/InventorySummary.tsx"], ["inventory_store"]),
                make_task("compose_inventory_app", "Compose inventory app shell", "Wire inventory screens into src/App.tsx.", ["src/App.tsx"], ["inventory_components"]),
            ],
            "crud_app": [
                make_task("crud_types", "Define CRUD entity model", "Create a primary entity type and seed records.", ["src/types.ts", "src/data/seedRecords.ts"]),
                make_task("crud_store", "Create CRUD state", "Implement localStorage-backed create, read, update, delete helpers.", ["src/hooks/useCrudStore.ts"], ["crud_types"]),
                make_task("crud_components", "Build CRUD interface", "Create list, form, edit, delete, and summary components.", ["src/components/CrudList.tsx", "src/components/CrudForm.tsx"], ["crud_store"]),
                make_task("compose_crud_app", "Compose CRUD app shell", "Wire CRUD components into src/App.tsx.", ["src/App.tsx"], ["crud_components"]),
            ],
        }

        tasks = recipes.get(signature.app_type)
        if not tasks:
            return None

        graph = TaskGraph()
        for task in tasks:
            graph.add_task(task)
        return graph

    @staticmethod
    async def create_plan(prompt: str, ecosystem_label: str, project_map: ProjectMap) -> TaskGraph:
        # Clean prompt of Task list and Implementation plan to let planning engine map clean, feature-based tasks
        clean_prompt = prompt
        if "Task list:" in clean_prompt:
            clean_prompt = clean_prompt.split("Task list:")[0].strip()
        if "Implementation plan:" in clean_prompt:
            clean_prompt = clean_prompt.split("Implementation plan:")[0].strip()

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
            deterministic = PlanningEngine._deterministic_plan(prompt)
            if deterministic is not None:
                return deterministic

            # Fallback task if planner fails to respond with valid JSON
            import traceback
            traceback.print_exc()
            graph = TaskGraph()
            task = ExecutionTask(
                id="fallback_task",
                title="Fallback Monolithic Generation",
                description=f"Planner failed to parse JSON: {e}. Executing standard fallback generation.",
                validation_contract=ValidationContract(success_criteria=["fallback_success"])
            )
            graph.add_task(task)
            return graph
