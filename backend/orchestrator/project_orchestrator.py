import logging
import asyncio
from dataclasses import dataclass, field

from backend.agent.parser import ParseError, parse_ai_response
from backend.agent.tools import write_file, append_file
from backend.models.schemas import GenerateRequest, GenerateResponse, ProjectType
from backend.prompts.templates import (
    SYSTEM_GENERATE,
    SYSTEM_REPAIR,
    build_generate_prompt,
    build_repair_prompt,
)
from backend.sandbox.executor import stream_command_async, run_dev_server_async
from backend.services.ai_service import complete
from backend.sockets.manager import emit_agent_state, emit_terminal_line, emit_agent_activity
from backend.templates.registry import scaffold_template

logger = logging.getLogger(__name__)

import datetime

def _create_governance_files(project_id: str, prompt: str):
    ts = datetime.datetime.now().isoformat()
    write_file(project_id, "README.md", f"# Project: {project_id}\n\n## Overview\nGenerated from prompt:\n> {prompt}\n\n## Stack\n- Vite\n- React\n- TypeScript\n- TailwindCSS\n\n## How to run\n```bash\nnpm install\nnpm run dev\n```\n\nGenerated at: {ts}")
    write_file(project_id, "TASK.md", "# Tasks\n\n## Active Tasks\n- Setup basic infrastructure\n\n## Pending Tasks\n- Feature implementation\n\n## Completed Tasks\n- [x] Initial scaffolding")
    write_file(project_id, "PLAN.md", "# Implementation Plan\n\n## Phases\n1. Scaffolding (Current)\n2. Dependency Installation\n3. Build and Test\n4. Auto Repair\n5. Launch Dev Server")
    write_file(project_id, "ARCHITECTURE_MAP.md", "# Architecture Map\n\n## Folder Structure\n- `src/` - React application code\n- `public/` - Static assets\n\n## Components\n- App.tsx: Main entry point\n- main.tsx: React DOM mounting")
    write_file(project_id, "ERROR_LOG.md", f"# Error Log\n\nInitialized at {ts}.\n")
    write_file(project_id, "WORKLOG.md", f"# Work Log\n\nInitialized at {ts}.\n- Project scaffolded.\n")

async def _log_work_async(project_id: str, message: str):
    await asyncio.to_thread(append_file, project_id, "WORKLOG.md", f"- {message}")
    try:
        await emit_agent_activity(message, project_id)
    except Exception:
        pass

async def _log_error_async(project_id: str, error: str):
    ts = datetime.datetime.now().isoformat()
    await asyncio.to_thread(append_file, project_id, "ERROR_LOG.md", f"## Error at {ts}\n\n```\n{error}\n```\n")


async def generate_project_async(req: GenerateRequest) -> GenerateResponse:
    """
    Asynchronous generation pipeline with strict template scaffolding and validation.
    """
    logger.info("Starting async generation for project=%s type=%s", req.project_id, req.project_type)

    # ── Step 0: Planning ──────────────────────────────────────────────────────
    await emit_agent_state("planning", req.project_id)
    await emit_terminal_line("AI Planning...", "info", req.project_id)
    await emit_agent_activity("Planning project structure...", req.project_id)

    # ── Step 1: Scaffold Template ─────────────────────────────────────────────
    await emit_agent_state("scaffolding", req.project_id)
    await emit_terminal_line("Scaffolding base template (vite-react-ts)...", "info", req.project_id)
    try:
        # Defaulting to vite-react-ts for stability
        scaffold_template(req.project_id, "vite-react-ts")
    except Exception as e:
        await emit_agent_state("failed", req.project_id)
        await emit_terminal_line(f"Failed to scaffold template: {e}", "stderr", req.project_id)
        return GenerateResponse(success=False, project_id=req.project_id, error=str(e))

    await emit_terminal_line("Creating Workspace Governance files...", "info", req.project_id)
    await asyncio.to_thread(_create_governance_files, req.project_id, req.prompt)
    await emit_terminal_line("Workspace Governance files generated.", "info", req.project_id)


    # ── Step 1: Generate Features ─────────────────────────────────────────────
    await emit_terminal_line(f"Starting AI feature generation: {req.prompt[:50]}...", "info", req.project_id)
    
    user_prompt = build_generate_prompt(req.prompt, req.project_type)

    try:
        raw = await asyncio.to_thread(complete, SYSTEM_GENERATE, user_prompt)
    except Exception as e:
        await emit_agent_state("failed", req.project_id)
        await emit_terminal_line(f"AI API error: {e}", "stderr", req.project_id)
        await _log_error_async(req.project_id, f"AI generation error: {e}")
        return GenerateResponse(success=False, project_id=req.project_id, error=str(e))

    # ── Step 2: Parse ─────────────────────────────────────────────────────────
    await emit_terminal_line("Validating and parsing generated files using deterministic protocol...", "info", req.project_id)
    try:
        files = parse_ai_response(raw)
        await emit_terminal_line(f"Successfully parsed {len(files)} files via protocol.", "info", req.project_id)
    except ParseError as e:
        await emit_agent_state("failed", req.project_id)
        await emit_terminal_line(f"Parse error: {e}", "stderr", req.project_id)
        await _log_error_async(req.project_id, f"Parse error: {e}\n\nRAW OUTPUT:\n{raw}")
        return GenerateResponse(success=False, project_id=req.project_id, error=str(e))

    # ── Step 3: Write ─────────────────────────────────────────────────────────
    await emit_agent_state("writing", req.project_id)
    written = []
    for f in files:
        try:
            path = await asyncio.to_thread(write_file, req.project_id, f.path, f.content)
            written.append(path)
            await emit_terminal_line(f"Written: {f.path}", "info", req.project_id)
            await _log_work_async(req.project_id, f"Created {f.path}")
        except ValueError as e:
            await emit_terminal_line(f"Skipping {f.path}: {e}", "stderr", req.project_id)
            await _log_error_async(req.project_id, f"Skipped file writing {f.path}: {e}")

    # ── Step 4: Install ───────────────────────────────────────────────────────
    await emit_agent_state("installing", req.project_id)
    install_res = await stream_command_async(req.project_id, "install")
    
    if not install_res.success:
        await emit_agent_state("failed", req.project_id)
        await _log_error_async(req.project_id, f"NPM Install failed:\n{install_res.stderr}\n{install_res.error}")
        return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=install_res.error)
    
    await _log_work_async(req.project_id, "Dependencies installed successfully.")

    # ── Step 5: Build + Auto Repair ───────────────────────────────────────────
    await emit_agent_state("building", req.project_id)
    
    repair_attempts = 0
    max_repairs = req.max_repair_attempts if hasattr(req, 'max_repair_attempts') else 3
    
    build_success = False
    
    for attempt in range(max_repairs + 1):
        build_res = await stream_command_async(req.project_id, "build")
        
        if build_res.success:
            build_success = True
            break
            
        if attempt >= max_repairs:
            await emit_agent_state("failed", req.project_id)
            error_summary = build_res.stderr or build_res.error or "Unknown build error"
            await _log_error_async(req.project_id, f"Build permanently failed after repairs:\n{error_summary}")
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=f"Build failed after {repair_attempts} repairs.\n{error_summary}")
            
        # Repair Loop
        repair_attempts += 1
        await emit_agent_state("repairing", req.project_id)
        await emit_terminal_line(f"Build failed. Initiating AI Auto-Repair {repair_attempts}/{max_repairs}...", "info", req.project_id)
        await _log_error_async(req.project_id, f"Build failed (Attempt {repair_attempts}). Starting auto-repair.\n{build_res.stderr}")
        
        build_error = f"STDOUT:\n{build_res.stdout}\n\nSTDERR:\n{build_res.stderr}\n\nERROR:\n{build_res.error}"
        repair_prompt = build_repair_prompt(req.prompt, build_error, req.project_type)
        
        try:
            raw_patch = await asyncio.to_thread(complete, SYSTEM_REPAIR, repair_prompt)
            patch_files = parse_ai_response(raw_patch)
            
            for pf in patch_files:
                path = await asyncio.to_thread(write_file, req.project_id, pf.path, pf.content)
                if path not in written:
                    written.append(path)
                await emit_terminal_line(f"Patched: {pf.path}", "info", req.project_id)
                await _log_work_async(req.project_id, f"Repaired {pf.path}")
                
        except Exception as e:
            await emit_agent_state("failed", req.project_id)
            await emit_terminal_line(f"Repair failed: {e}", "stderr", req.project_id)
            await _log_error_async(req.project_id, f"Auto-repair API error: {e}")
            return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=str(e))
            
        await emit_agent_state("building", req.project_id)
        
    if not build_success:
        await emit_agent_state("failed", req.project_id)
        return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error="Build permanently failed.")
        
    await _log_work_async(req.project_id, "Build succeeded after repairs.")

    # ── Step 6: Dev Server ────────────────────────────────────────────────────
    await emit_agent_state("launching", req.project_id)
    await emit_terminal_line("Starting Dev Server...", "info", req.project_id)
    dev_res = await run_dev_server_async(req.project_id)
    
    if not dev_res.success:
        await emit_agent_state("failed", req.project_id)
        await _log_error_async(req.project_id, f"Dev server failed to start:\n{dev_res.error}")
        return GenerateResponse(success=False, project_id=req.project_id, files_written=written, error=dev_res.error)

    # Success
    await emit_agent_state("success", req.project_id)
    await emit_terminal_line("Validation complete. System is stable.", "info", req.project_id)
    await _log_work_async(req.project_id, "Dev server launched successfully. System is stable.")
    
    return GenerateResponse(success=True, project_id=req.project_id, files_written=written)

def generate_project(req: GenerateRequest) -> GenerateResponse:
    """Synchronous fallback."""
    pass
