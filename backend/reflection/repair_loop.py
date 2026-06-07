import logging
import asyncio
from typing import List, Optional

from backend.agent.parser import parse_ai_response, ParseError
from backend.agent.tools import write_file
from backend.services.ai_service import complete
from backend.sockets.manager import emit_agent_state, emit_terminal_line
from backend.runtime_contract import RuntimeErrorCode
from backend.templates.react_vite_contract import classify_react_vite_failure
from backend.reflection.reflection_engine import ReflectionEngine

logger = logging.getLogger(__name__)


class RepairAnalyzer:
    """Classifies errors and generates targeted fixes."""
    
    @staticmethod
    def classify_failure(stderr: str, stdout: str) -> str:
        deterministic_type = classify_react_vite_failure(stdout, stderr)
        if deterministic_type != RuntimeErrorCode.E_BUILD_FAILURE.value:
            return deterministic_type

        text = (stderr + " " + stdout).lower()
        if "ts2345" in text and ("setstateaction" in text or "stateaction" in text) and "assignable" in text:
            return "ts2345_nullable_state"
        if ("ts2741" in text or "ts2739" in text or "ts2322" in text) and "missing" in text and "properties" in text:
            return "schema_drift_missing_properties"
        if "property" in text and "is missing" in text and "required" in text:
            return "schema_drift_missing_properties"
        if "tsconfig" in text or "typescript" in text or "ts6" in text:
            return "typescript_config"
        if "npm err!" in text or "enoent" in text:
            return "dependency_missing"
        if "syntax error" in text or "unexpected token" in text:
            return "syntax_error"
        if "module not found" in text or "cannot resolve" in text:
            return "import_error"
        return "general_build_error"


async def attempt_repair(
    project_id: str, 
    original_prompt: str, 
    ecosystem_label: str, 
    stdout: str, 
    stderr: str, 
    attempt: int, 
    max_repairs: int,
    written_files: List[str],
    run_id: Optional[str] = None
) -> bool:
    """
    Attempts to repair a failed execution.
    Returns True if the patch was successfully generated and applied (does not guarantee build success, just patch success).
    """
    # Clean prompt of Task list and Implementation plan to prevent LLM confusion during repair
    clean_prompt = original_prompt
    if "Task list:" in clean_prompt:
        clean_prompt = clean_prompt.split("Task list:")[0].strip()
    if "Implementation plan:" in clean_prompt:
        clean_prompt = clean_prompt.split("Implementation plan:")[0].strip()

    await emit_agent_state("repairing", project_id)
    await emit_terminal_line(f"[Reflection] Analyzing failure (Attempt {attempt}/{max_repairs})...", "info", project_id)
    
    failure_type = RepairAnalyzer.classify_failure(stderr, stdout)
    await emit_terminal_line(f"[Reflection] Classified error as: {failure_type}", "info", project_id)
    cycle = ReflectionEngine.latest_cycle(project_id, run_id)
    if not cycle:
        cycle = ReflectionEngine.start_cycle(project_id, run_id, "build", "build")
        validation = {
            "status": "failed",
            "stage": "build",
            "command": "build",
            "exit_code": None,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
            "error": None,
        }
        errors = ReflectionEngine.collect_errors(validation)
        root_cause = ReflectionEngine.analyze_root_cause(errors, validation)
        repair_plan = ReflectionEngine.plan_repair(root_cause, validation)
        ReflectionEngine.attach_errors_analysis_plan(project_id, cycle["id"], errors, root_cause, repair_plan)
    else:
        root_cause = cycle.get("root_cause") or {"category": failure_type, "confidence": 0.5}
        repair_plan = cycle.get("repair_plan") or ReflectionEngine.plan_repair(root_cause, cycle.get("validation") or {})
    
    # Gather file content for context
    files_context = ""
    if written_files:
        from pathlib import Path
        for file_path in written_files:
            try:
                p = Path(file_path)
                if p.exists() and p.is_file():
                    content = p.read_text(encoding="utf-8")
                    parts = list(p.parts)
                    if project_id in parts:
                        idx = parts.index(project_id)
                        if idx + 1 < len(parts) and parts[idx+1].startswith("run_"):
                            rel_path = "/".join(parts[idx+2:])
                        else:
                            rel_path = "/".join(parts[idx+1:])
                    else:
                        rel_path = p.name
                    files_context += f"\n--- FILE: {rel_path} ---\n{content}\n"
            except Exception as e:
                logger.warning(f"Could not read file {file_path} for context: {e}")

    extra_instruction = ""
    if failure_type == "ts2345_nullable_state":
        extra_instruction = (
            "\n[CRITICAL INSTRUCTION FOR TS2345 NULLABLE/PARTIAL STATE ERROR]\n"
            "This error is caused by updating React form state by spreading a nullable/optional object, making fields optional/undefined.\n"
            "To fix this, you must NOT spread nullable/optional objects directly in state updates.\n"
            "Follow these rules:\n"
            "1. Define a clear, non-nullable Form Type (separate from the Entity/Database Type which has ID).\n"
            "2. Initialize the state with a complete default object (all fields populated, e.g. empty strings, 0, etc.).\n"
            "3. Do NOT use null or Partial<Type> as the state type. Keep the form state as a plain object of the Form Type.\n"
            "4. When updating, spread the existing non-nullable state object, e.g. `setForm(prev => ({ ...prev, [field]: value }))`.\n"
            "Example fix:\n"
            "```typescript\n"
            "interface ProductForm {\n"
            "  name: string;\n"
            "  price: number;\n"
            "  description: string;\n"
            "}\n"
            "const emptyForm: ProductForm = { name: '', price: 0, description: '' };\n"
            "const [form, setForm] = useState<ProductForm>(emptyForm);\n"
            "// When editing:\n"
            "setForm({ name: prod.name, price: prod.price, description: prod.description });\n"
            "```\n"
        )
    elif failure_type == "typescript_config":
        extra_instruction = (
            "\n[CRITICAL INSTRUCTION FOR TYPESCRIPT CONFIG LOAD ERROR]\n"
            "The PostCSS or Vite build failed because it is trying to load TypeScript config files (like tailwind.config.ts or postcss.config.ts) but 'ts-node' is not installed.\n"
            "To fix this, you MUST add 'ts-node' to the devDependencies or dependencies in `package.json`.\n"
            "Example package.json devDependencies edit:\n"
            "```json\n"
            "  \"devDependencies\": {\n"
            "    \"ts-node\": \"^10.9.2\"\n"
            "  }\n"
            "```\n"
        )
    elif failure_type == "schema_drift_missing_properties":
        extra_instruction = (
            "\n[CRITICAL INSTRUCTION FOR SCHEMA DRIFT / MISSING TYPE PROPERTIES]\n"
            "This error usually means an existing interface/type is correct, but one or more object literals no longer satisfy it.\n"
            "To fix this, you MUST:\n"
            "1. Find the existing type/interface definition first (for example Product, InventoryItem, or CrudEntity).\n"
            "2. Find every object literal or seed array typed as that interface.\n"
            "3. Add the missing required properties to the object literals using sensible values consistent with existing consumers.\n"
            "4. Do NOT add random optional fields to the interface just to silence the compiler.\n"
            "5. Do NOT create a second schema or rename the type.\n"
            "6. Preserve existing consumers and imports.\n"
        )

    repair_prompt = (
        f"The {ecosystem_label} project failed to build with a {failure_type}.\n"
        f"Structured root cause estimate: {root_cause.get('category')} (confidence={root_cause.get('confidence')}).\n"
        f"Ranked repair plan: {repair_plan}.\n"
        f"{extra_instruction}"
        f"Original user request: {clean_prompt}\n\n"
        f"Build STDOUT:\n{stdout[-1000:]}\n\n"
        f"Build STDERR:\n{stderr[-1000:]}\n\n"
        f"Here is the current content of the generated files:\n"
        f"{files_context}\n\n"
        f"Analyze the logs and the files, identify the cause of the compilation failure, and generate the specific files needed to fix the error.\n"
        f"You MUST also generate a `REPAIR_DECISION.md` file (using the standard format) documenting:\n"
        f"- Error Diagnosis: why the build failed\n"
        f"- Alternatives Considered: other ways to solve it\n"
        f"- Blast-radius Analysis: how the change affects the rest of the application components\n\n"
        f"Ensure all file edits are complete and syntactically correct.\n"
        f"Use the ===FILE:relative/path.ext=== ... ===END=== format."
    )
    
    try:
        raw_patch = await asyncio.to_thread(complete, "You are an autonomous debugging agent. Fix the error by providing patched files.", repair_prompt)
        patch_files = parse_ai_response(raw_patch)
        
        if not patch_files:
            await emit_terminal_line(f"[Reflection] AI did not suggest any file changes.", "stderr", project_id)
            return False, False
            
        for pf in patch_files:
            path = await asyncio.to_thread(write_file, project_id, pf.path, pf.content, run_id)
            if path not in written_files:
                written_files.append(path)
            await emit_terminal_line(f"[Repair] Applied patch to {pf.path}", "info", project_id)
            
        package_json_modified = any(pf.path.endswith("package.json") for pf in patch_files)
        ReflectionEngine.record_repair_execution(
            project_id,
            run_id,
            success=True,
            attempt=attempt,
            patched_files=[pf.path for pf in patch_files],
            package_json_modified=package_json_modified,
            message=f"Patched {len(patch_files)} files.",
        )
        
        from backend.memory.reflection_memory import ReflectionMemory
        ReflectionMemory.record_repair(
            project_id=project_id,
            failure_type=failure_type,
            stderr=stderr,
            stdout=stdout,
            patch_summary=f"Patched {len(patch_files)} files.",
            success=True
        )
        return True, package_json_modified
        
    except ParseError as pe:
        await emit_terminal_line(f"[Reflection] Patch parse error: {pe}", "stderr", project_id)
        ReflectionEngine.record_repair_execution(
            project_id,
            run_id,
            success=False,
            attempt=attempt,
            patched_files=[],
            message=f"Patch parse error: {pe}",
        )
        from backend.memory.reflection_memory import ReflectionMemory
        ReflectionMemory.record_repair(project_id, failure_type, stderr, stdout, str(pe), False)
        return False, False
    except Exception as e:
        await emit_terminal_line(f"[Reflection] Reflection AI error: {e}", "stderr", project_id)
        ReflectionEngine.record_repair_execution(
            project_id,
            run_id,
            success=False,
            attempt=attempt,
            patched_files=[],
            message=f"Reflection AI error: {e}",
        )
        return False, False
