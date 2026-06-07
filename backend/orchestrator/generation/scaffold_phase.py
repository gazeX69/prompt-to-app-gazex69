import asyncio
import datetime
import hashlib
import re

from backend.agent.tools import create_project, write_file
from backend.sockets.manager import emit_agent_state, emit_terminal_line
from backend.templates.registry import scaffold_template

from .lifecycle import _ecosystem_label


def _remove_existing_runtime_truth_markers(content: str) -> str:
    cleaned = re.sub(
        r"\s*<div\b[^>]*\bid=[\"']runtime-truth[\"'][^>]*/>\s*",
        "\n",
        content,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*<div\b[^>]*\bid=[\"']runtime-truth[\"'][^>]*>\s*</div>\s*",
        "\n",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned)

def _create_governance_files(project_id: str, run_id: str, prompt: str, ecosystem: str):
    ts = datetime.datetime.now().isoformat()
    eco_label = _ecosystem_label(ecosystem)
    write_file(project_id, "README.md", f"# Project: {project_id}\n\n## Overview\nGenerated from prompt:\n> {prompt}\n\n## Stack\n- {eco_label}\n\n## How to run\nSee PLAN.md for details.\n\nGenerated at: {ts}", run_id)
    write_file(project_id, "TASK.md", "# Tasks\n\n## Active Tasks\n- Setup basic infrastructure\n\n## Pending Tasks\n- Feature implementation\n\n## Completed Tasks\n- [x] Initial scaffolding", run_id)
    write_file(project_id, "PLAN.md", f"# Implementation Plan\n\n## Phases\n1. Scaffolding (Current)\n2. {'Dependency Installation' if ecosystem in ('react-vite', 'node-backend') else 'File Generation'}\n3. {'Build and Test' if ecosystem in ('react-vite', 'node-backend') else 'Validation'}\n4. Launch Dev Server", run_id)
    write_file(project_id, "ARCHITECTURE_MAP.md", f"# Architecture Map\n\n## Stack\n- {eco_label}\n\n## Project Structure\nRefer to generated files.", run_id)
    write_file(project_id, "ERROR_LOG.md", f"# Error Log\n\nInitialized at {ts}.\n", run_id)
    write_file(project_id, "WORKLOG.md", f"# Work Log\n\nInitialized at {ts}.\n- Project scaffolded.\n", run_id)



async def _inject_truth_markers(project_id: str, run_id: str, prompt: str, ecosystem: str):
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    
    # Generate marker strings
    marker_html = f'\n    <meta name="ai-run-id" content="{run_id}">\n    <meta name="ai-project-id" content="{project_id}">\n    <meta name="ai-prompt-hash" content="{prompt_hash}">\n'
    dom_marker = f'<div id="runtime-truth" data-run-id="{run_id}" data-project-id="{project_id}" data-prompt-hash="{prompt_hash}" style={{{{ display: "none" }}}} />'
    dom_marker_html = f'<div id="runtime-truth" data-run-id="{run_id}" data-project-id="{project_id}" data-prompt-hash="{prompt_hash}" style="display:none;"></div>'

    from backend.agent.tools import read_file, write_file

    if ecosystem == "react-vite":
        # 1. HTML Truth Marker
        try:
            html_content = await asyncio.to_thread(read_file, project_id, "index.html", run_id)
            if "<head>" in html_content:
                html_content = html_content.replace("<head>", f"<head>{marker_html}")
            else:
                html_content = marker_html + html_content
            await asyncio.to_thread(write_file, project_id, "index.html", html_content, run_id)
            msg = f"[TruthMarker] ecosystem={ecosystem} injecting into index.html"
            print(msg)
            await emit_terminal_line(msg, "info", project_id)
        except Exception as e:
            err = f"[TruthMarker] HTML injection failed: {e}"
            print(err)
            await emit_terminal_line(err, "stderr", project_id)



        # 2. DOM Truth Marker
        try:
            main_content = await asyncio.to_thread(read_file, project_id, "src/main.tsx", run_id)
            main_content = _remove_existing_runtime_truth_markers(main_content)
            if "<App />" in main_content:
                main_content = main_content.replace("<App />", f"<>\n      {dom_marker}\n      <App />\n    </>")
                await asyncio.to_thread(write_file, project_id, "src/main.tsx", main_content, run_id)
                msg = f"[TruthMarker] ecosystem={ecosystem} injecting into src/main.tsx"
                print(msg)
                await emit_terminal_line(msg, "info", project_id)
        except Exception as e:
            err = f"[TruthMarker] DOM injection failed: {e}"
            print(err)
            await emit_terminal_line(err, "stderr", project_id)

    elif ecosystem == "php-basic":
        for target_file in ["index.php", "index.html"]:
            try:
                content = await asyncio.to_thread(read_file, project_id, target_file, run_id)
                
                if target_file.endswith(".php"):
                    php_errors = "<?php\nerror_reporting(E_ALL);\nini_set('display_errors', '1');\n?>\n"
                    content = php_errors + content

                if "<head>" in content:
                    content = content.replace("<head>", f"<head>{marker_html}")
                else:
                    content = marker_html + content
                
                if "<body>" in content:
                    content = content.replace("<body>", f"<body>\n{dom_marker_html}")
                else:
                    content += f"\n{dom_marker_html}"
                    
                await asyncio.to_thread(write_file, project_id, target_file, content, run_id)
                msg = f"[TruthMarker] ecosystem={ecosystem} injecting into {target_file}"
                print(msg)
                await emit_terminal_line(msg, "info", project_id)
                break
            except FileNotFoundError:
                continue
            except Exception as e:
                err = f"[TruthMarker] ecosystem={ecosystem} injection failed: {e}"
                print(err)
                await emit_terminal_line(err, "stderr", project_id)

    elif ecosystem == "laravel":
        for target_file in ["resources/views/layouts/app.blade.php", "resources/views/welcome.blade.php"]:
            try:
                content = await asyncio.to_thread(read_file, project_id, target_file, run_id)
                if "<head>" in content:
                    content = content.replace("<head>", f"<head>{marker_html}")
                if "<body>" in content:
                    content = content.replace("<body>", f"<body>\n{dom_marker_html}")
                await asyncio.to_thread(write_file, project_id, target_file, content, run_id)
                msg = f"[TruthMarker] ecosystem={ecosystem} injecting into {target_file}"
                print(msg)
                await emit_terminal_line(msg, "info", project_id)
                break
            except FileNotFoundError:
                continue

    else:
        # Fallback static HTML
        try:
            target_file = "index.html"
            content = await asyncio.to_thread(read_file, project_id, target_file, run_id)
            if "<head>" in content:
                content = content.replace("<head>", f"<head>{marker_html}")
            if "<body>" in content:
                content = content.replace("<body>", f"<body>\n{dom_marker_html}")
            await asyncio.to_thread(write_file, project_id, target_file, content, run_id)
            msg = f"[TruthMarker] ecosystem={ecosystem} injecting into {target_file}"
            print(msg)
            await emit_terminal_line(msg, "info", project_id)
        except Exception as e:
            err = f"[TruthMarker] fallback injection failed: {e}"
            print(err)
            await emit_terminal_line(err, "stderr", project_id)


async def scaffold_generation_workspace(
    req,
    run_id: str,
    skill_name: str,
    hints: dict,
    initialized_from_current_state: bool,
) -> str | None:
    if not initialized_from_current_state:
        create_project(req.project_id, run_id)
    create_project(req.project_id, "latest")
    if hints.get("requires_template", False):
        template_name = hints.get("template_name", "")
        if template_name and not initialized_from_current_state:
            await emit_terminal_line(f"[Template] Scaffolding {template_name}...", "info", req.project_id)
            try:
                scaffold_template(req.project_id, template_name, run_id)
                scaffold_template(req.project_id, template_name, "latest")
                # Ensure src/vite-env.d.ts is present for Vite + TS client types
                if skill_name == "react-vite":
                    write_file(req.project_id, "src/vite-env.d.ts", '/// <reference types="vite/client" />\n', run_id)
                    write_file(req.project_id, "src/vite-env.d.ts", '/// <reference types="vite/client" />\n', "latest")
            except Exception as e:
                await emit_agent_state("failed", req.project_id)
                await emit_terminal_line(f"[Template] Failed early scaffolding: {e}", "stderr", req.project_id)
                return str(e)
        elif initialized_from_current_state:
            await emit_terminal_line(
                "[Template] Skipping template scaffold for MODIFY; preserving copied current project files.",
                "info",
                req.project_id,
            )
    else:
        await emit_terminal_line(f"[Template] No template needed for {skill_name}, creating empty workspace", "info", req.project_id)
    return None
