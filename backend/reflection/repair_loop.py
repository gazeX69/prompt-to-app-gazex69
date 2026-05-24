import logging
import asyncio
from typing import List, Optional

from backend.agent.parser import parse_ai_response, ParseError
from backend.agent.tools import write_file
from backend.services.ai_service import complete
from backend.sockets.manager import emit_agent_state, emit_terminal_line
from backend.runtime_contract import RuntimeErrorCode
from backend.templates.react_vite_contract import classify_react_vite_failure

logger = logging.getLogger(__name__)


class RepairAnalyzer:
    """Classifies errors and generates targeted fixes."""
    
    @staticmethod
    def classify_failure(stderr: str, stdout: str) -> str:
        deterministic_type = classify_react_vite_failure(stdout, stderr)
        if deterministic_type != RuntimeErrorCode.E_BUILD_FAILURE.value:
            return deterministic_type

        text = (stderr + " " + stdout).lower()
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
    written_files: List[str]
) -> bool:
    """
    Attempts to repair a failed execution.
    Returns True if the patch was successfully generated and applied (does not guarantee build success, just patch success).
    """
    await emit_agent_state("repairing", project_id)
    await emit_terminal_line(f"[Reflection] Analyzing failure (Attempt {attempt}/{max_repairs})...", "info", project_id)
    
    failure_type = RepairAnalyzer.classify_failure(stderr, stdout)
    await emit_terminal_line(f"[Reflection] Classified error as: {failure_type}", "info", project_id)
    
    repair_prompt = (
        f"The {ecosystem_label} project failed to build with a {failure_type}.\n"
        f"Original user request: {original_prompt}\n\n"
        f"Build STDOUT:\n{stdout[-1000:]}\n\n"
        f"Build STDERR:\n{stderr[-1000:]}\n\n"
        f"Analyze the logs and generate ONLY the specific files needed to fix the error.\n"
        f"Use the ===FILE:relative/path.ext=== ... ===END=== format."
    )
    
    try:
        raw_patch = await asyncio.to_thread(complete, "You are an autonomous debugging agent. Fix the error by providing patched files.", repair_prompt)
        patch_files = parse_ai_response(raw_patch)
        
        if not patch_files:
            await emit_terminal_line(f"[Reflection] AI did not suggest any file changes.", "stderr", project_id)
            return False
            
        for pf in patch_files:
            path = await asyncio.to_thread(write_file, project_id, pf.path, pf.content)
            if path not in written_files:
                written_files.append(path)
            await emit_terminal_line(f"[Repair] Applied patch to {pf.path}", "info", project_id)
            
        from backend.memory.reflection_memory import ReflectionMemory
        ReflectionMemory.record_repair(
            project_id=project_id,
            failure_type=failure_type,
            stderr=stderr,
            stdout=stdout,
            patch_summary=f"Patched {len(patch_files)} files.",
            success=True
        )
        return True
        
    except ParseError as pe:
        await emit_terminal_line(f"[Reflection] Patch parse error: {pe}", "stderr", project_id)
        from backend.memory.reflection_memory import ReflectionMemory
        ReflectionMemory.record_repair(project_id, failure_type, stderr, stdout, str(pe), False)
        return False
    except Exception as e:
        await emit_terminal_line(f"[Reflection] Reflection AI error: {e}", "stderr", project_id)
        return False
