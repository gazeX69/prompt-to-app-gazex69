"""
Terminal execution sandbox.

Runs commands inside a specific project workspace directory.
Supports both whitelist commands (legacy) and dynamic command arrays (skill-driven).
Every command logs its cwd explicitly. Success is determined by exit code, not stderr content.
Dev server readiness detection monitors both stdout AND stderr.

On Windows, uvicorn may use SelectorEventLoop which does NOT support
asyncio.create_subprocess_exec. This module detects the event loop type
and falls back to subprocess.Popen with run_in_executor for streaming.
"""

import logging
import subprocess
import shutil
import shlex
import sys
import asyncio
import re
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

from backend.agent.tools import _safe_project_path, WORKSPACE_ROOT
from backend.models.schemas import ExecuteResponse
from backend.sockets.manager import (
    emit_agent_state,
    emit_preview_ready,
    emit_runtime_error,
    emit_runtime_lifecycle_event,
    emit_terminal_line,
)
from backend.runtime_contract import RuntimeErrorCode

# Legacy whitelist — kept for backward compatibility
COMMAND_WHITELIST: dict[str, str] = {
    "install": "npm install --no-progress",
    "build": "npm run build --no-progress",
    "dev": "npm run dev",
    "lint": "npm run lint",
    "test": "npm run test",
}

# Minimal env — no CI=true (breaks npm on Windows)
_MINIMAL_ENV = {}

import time
import socket
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class RuntimeEntry:
    project_id: str
    run_id: str
    process_pid: int
    cwd: str
    assigned_port: Optional[str]
    started_at: float
    runtime_type: str
    preview_url: Optional[str]
    process_status: str
    popen: subprocess.Popen
    last_healthcheck: Optional[float] = None
    error: Optional[str] = None

_runtime_registry: Dict[str, RuntimeEntry] = {}
_runtime_status_snapshots: Dict[str, dict] = {}

DEFAULT_TIMEOUT_SECONDS = 180


async def _emit_runtime_lifecycle(
    event_type: str,
    project_id: str,
    run_id: str,
    message: str,
    *,
    selected_port: int | str | None = None,
    process_pid: int | None = None,
    error: dict | None = None,
) -> None:
    payload = {
        "type": event_type,
        "timestamp": int(time.time() * 1000),
        "workspaceId": project_id,
        "sessionId": run_id,
        "message": message,
    }
    if selected_port is not None:
        payload["selectedPort"] = int(selected_port)
    if process_pid is not None:
        payload["processPid"] = process_pid
    if error is not None:
        payload["error"] = error
    await emit_runtime_lifecycle_event(payload)


def _runtime_entry_to_status(entry: RuntimeEntry) -> dict:
    return {
        "project_id": entry.project_id,
        "run_id": entry.run_id,
        "status": entry.process_status,
        "port": int(entry.assigned_port) if entry.assigned_port else None,
        "pid": entry.process_pid,
        "url": entry.preview_url,
        "started_at": entry.started_at,
        "last_healthcheck": entry.last_healthcheck,
        "error": entry.error,
    }


def _record_runtime_status(entry: RuntimeEntry | dict) -> dict:
    status = _runtime_entry_to_status(entry) if isinstance(entry, RuntimeEntry) else entry
    project_id = status.get("project_id")
    if project_id:
        _runtime_status_snapshots[project_id] = status
    return status


def _fail_runtime_readback(project_id: str, entry: RuntimeEntry, error: str) -> dict:
    failed_status = {
        "project_id": entry.project_id,
        "run_id": entry.run_id,
        "status": "failed",
        "port": None,
        "pid": entry.process_pid,
        "url": None,
        "started_at": entry.started_at,
        "last_healthcheck": time.time(),
        "error": error,
    }
    _record_runtime_status(failed_status)
    if _runtime_registry.get(project_id) is entry:
        del _runtime_registry[project_id]
    return failed_status


def _refresh_runtime_entry_status(project_id: str, entry: RuntimeEntry) -> dict:
    exit_code = entry.popen.poll()
    if exit_code is not None:
        return _fail_runtime_readback(
            project_id,
            entry,
            f"Runtime process exited unexpectedly (Exit {exit_code})",
        )

    if entry.process_status != "running":
        return _runtime_entry_to_status(entry)

    if not entry.preview_url:
        return _fail_runtime_readback(project_id, entry, "Runtime marked running without a preview URL")

    try:
        status, body = _fetch_text(entry.preview_url, timeout=1.0)
        entry.last_healthcheck = time.time()
        if status >= 400:
            return _fail_runtime_readback(project_id, entry, f"Runtime preview returned HTTP {status}")
        if f'content="{entry.run_id}"' not in body and f'data-run-id="{entry.run_id}"' not in body:
            return _fail_runtime_readback(
                project_id,
                entry,
                "Runtime preview did not contain the active run marker",
            )
        _record_runtime_status(entry)
        return _runtime_entry_to_status(entry)
    except Exception as e:
        return _fail_runtime_readback(project_id, entry, f"Runtime preview unreachable: {e}")


async def _emit_runtime_readback_failure(status: dict, entry: RuntimeEntry) -> None:
    project_id = status.get("project_id")
    run_id = status.get("run_id")
    error = status.get("error") or "Runtime failed during status readback"
    port = entry.assigned_port
    pid = status.get("pid")
    error_text = error.lower()
    is_process_exit = "process exited" in error_text
    lifecycle_type = "runtime.crashed" if is_process_exit else "runtime.healthcheck.failed"
    error_code = (
        RuntimeErrorCode.RUNTIME_PROCESS_CRASH
        if is_process_exit
        else RuntimeErrorCode.RUNTIME_DEVSERVER_UNREACHABLE
    )

    await emit_terminal_line(f"[RuntimeReadback] {error}", "stderr", project_id)
    await _emit_runtime_lifecycle(
        lifecycle_type,
        project_id,
        run_id,
        error,
        selected_port=port,
        process_pid=pid,
    )
    await emit_runtime_error(
        error_code,
        error,
        detail={"port": port, "pid": pid},
        project_id=project_id,
        run_id=run_id,
        source="runtime",
    )
    await emit_agent_state("failed", project_id)


async def get_runtime_status_for_readback(project_id: str) -> tuple[dict, bool]:
    entry = _runtime_registry.get(project_id)
    if not entry:
        return get_runtime_status(project_id), False

    status = _refresh_runtime_entry_status(project_id, entry)
    invalidated = status.get("status") == "failed" and _runtime_registry.get(project_id) is not entry
    if invalidated:
        await _emit_runtime_readback_failure(status, entry)
    return status, invalidated


def get_runtime_status(project_id: str | None = None) -> dict:
    if project_id:
        entry = _runtime_registry.get(project_id)
        if entry:
            return _refresh_runtime_entry_status(project_id, entry)
        if project_id in _runtime_status_snapshots:
            return _runtime_status_snapshots[project_id]
        return {
            "project_id": project_id,
            "run_id": None,
            "status": "stopped",
            "port": None,
            "pid": None,
            "url": None,
            "started_at": None,
            "last_healthcheck": None,
            "error": None,
        }

    return {
        "runtimes": [_refresh_runtime_entry_status(project_id, entry) for project_id, entry in list(_runtime_registry.items())]
    }

def _kill_process_tree(popen: subprocess.Popen, project_id: str) -> None:
    if popen.returncode is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(popen.pid)], capture_output=True)
        else:
            popen.kill()
    except Exception as e:
        print(f"Failed to kill process tree for {project_id}: {e}")


async def stop_runtime(project_id: str) -> dict:
    entry = _runtime_registry.get(project_id)
    if not entry:
        return get_runtime_status(project_id)

    await emit_terminal_line(f"[RuntimeStop] stopping runtime PID {entry.process_pid}", "info", project_id)
    await _emit_runtime_lifecycle(
        "runtime.stopping",
        project_id,
        entry.run_id,
        f"Stopping runtime PID {entry.process_pid}",
        selected_port=entry.assigned_port,
        process_pid=entry.process_pid,
    )
    _kill_process_tree(entry.popen, project_id)

    exited = await _wait_for_process_exit(entry.popen)
    port_released = True
    if entry.assigned_port and exited:
        port_released = await _wait_for_port_release(int(entry.assigned_port))

    if not exited or not port_released:
        entry.process_status = "failed"
        entry.error = "Runtime stop failed" if not exited else "Runtime port did not release"
        _record_runtime_status(entry)
        await _emit_runtime_lifecycle(
            "runtime.stop.failed",
            project_id,
            entry.run_id,
            entry.error,
            selected_port=entry.assigned_port,
            process_pid=entry.process_pid,
        )
        return _runtime_entry_to_status(entry)

    stopped_status = {
        "project_id": entry.project_id,
        "run_id": entry.run_id,
        "status": "stopped",
        "port": int(entry.assigned_port) if entry.assigned_port else None,
        "pid": entry.process_pid,
        "url": entry.preview_url,
        "started_at": entry.started_at,
        "last_healthcheck": entry.last_healthcheck,
        "error": None,
    }
    _record_runtime_status(stopped_status)
    del _runtime_registry[project_id]
    await emit_terminal_line("[RuntimeStop] runtime stopped", "info", project_id)
    await _emit_runtime_lifecycle(
        "runtime.stopped",
        project_id,
        entry.run_id,
        "Runtime stopped",
        selected_port=entry.assigned_port,
        process_pid=entry.process_pid,
    )
    return stopped_status


async def record_pre_runtime_failure(
    project_id: str,
    error: str,
    *,
    stage: str = "pre_runtime",
    run_id: str | None = None,
) -> dict:
    if project_id in _runtime_registry:
        await stop_runtime(project_id)

    status = {
        "project_id": project_id,
        "run_id": run_id,
        "status": "failed",
        "port": None,
        "pid": None,
        "url": None,
        "started_at": None,
        "last_healthcheck": int(time.time() * 1000),
        "error": f"{stage}: {error}" if stage else error,
    }
    _record_runtime_status(status)
    return status


async def _wait_for_process_exit(popen: subprocess.Popen, seconds: float = 10.0) -> bool:
    attempts = max(1, int(seconds / 0.25))
    for _ in range(attempts):
        if popen.poll() is not None:
            return True
        await asyncio.sleep(0.25)
    return popen.poll() is not None


async def _wait_for_port_release(port: int, seconds: float = 10.0) -> bool:
    attempts = max(1, int(seconds / 0.25))
    for _ in range(attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            return True
        except OSError:
            await asyncio.sleep(0.25)
    return False


def _fetch_text(url: str, timeout: float = 2.0) -> tuple[int, str]:
    res = urllib.request.urlopen(url, timeout=timeout)
    body = res.read().decode("utf-8", errors="replace")
    return int(getattr(res, "status", 200)), body


async def _wait_for_verified_runtime(
    url: str,
    run_id: str,
    project_id: str,
    *,
    timeout_seconds: float = 30.0,
) -> tuple[bool, str | None]:
    deadline = time.time() + timeout_seconds
    last_error: str | None = None

    while time.time() < deadline:
        try:
            status, body = await asyncio.to_thread(_fetch_text, url)
            if status >= 400:
                last_error = f"HTTP {status}"
            elif f'content="{run_id}"' in body or f'data-run-id="{run_id}"' in body:
                return True, None
            else:
                last_error = "served HTML did not contain the active run marker"
        except Exception as e:
            last_error = str(e)
        await asyncio.sleep(0.5)

    return False, last_error or "runtime did not become reachable"


def _resolve_executable(exe_name: str) -> str:
    """Resolve npm -> npm.cmd on Windows, php -> php.exe, etc."""
    exe_path = shutil.which(exe_name)
    if not exe_path and sys.platform == "win32":
        exe_path = shutil.which(f"{exe_name}.exe") or shutil.which(f"{exe_name}.cmd")
    return exe_path


def _resolve_npm_on_windows(exe_name: str) -> str:
    """On Windows, always prefer .cmd for npm to avoid ENOENT."""
    if sys.platform == "win32" and exe_name == "npm":
        npm_cmd = shutil.which("npm.cmd")
        if npm_cmd:
            return npm_cmd
    return _resolve_executable(exe_name)


def _check_required_files(project_id: str, required: list[str], run_id: str = None) -> str | None:
    """Check that all required files exist. Returns error message or None."""
    project_path = _safe_project_path(project_id, run_id)
    for f in required:
        if not (project_path / f).exists():
            return f"Required file missing: {project_id}/{run_id}/{f} — cannot proceed"
    return None


_ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


async def _stream_reader_sync(popen_pipe, type_str: str, project_id: str, lines_list: list[str], parser_callback=None, prefix: str = ""):
    """Read lines from a synchronous subprocess.PIPE asynchronously via run_in_executor."""
    loop = asyncio.get_running_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, popen_pipe.readline)
            if not line:
                break
            decoded = prefix + line.decode('utf-8', errors='replace').rstrip('\r\n')
            if not decoded.strip() and type_str != 'info':
                continue
            lines_list.append(decoded)
            await emit_terminal_line(decoded, type_str, project_id)
            if parser_callback:
                clean = _ANSI_RE.sub('', decoded)
                await parser_callback(clean)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await emit_terminal_line(f"Stream read error: {e}", "stderr", project_id)


async def _stream_reader(stream: asyncio.StreamReader, type_str: str, project_id: str, lines_list: list[str], parser_callback=None):
    """Read lines from an async StreamReader."""
    try:
        while True:
            line = await stream.readline()
            if not line:
                break
            decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
            if not decoded.strip() and type_str != 'info':
                continue
            lines_list.append(decoded)
            await emit_terminal_line(decoded, type_str, project_id)
            if parser_callback:
                clean = _ANSI_RE.sub('', decoded)
                await parser_callback(clean)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        await emit_terminal_line(f"Stream read error: {e}", "stderr", project_id)


def _start_dev_stream_reader_thread(
    popen_pipe,
    type_str: str,
    project_id: str,
    lines_list: list[str],
    loop: asyncio.AbstractEventLoop,
    parser_callback=None,
    prefix: str = "",
) -> threading.Thread:
    def reader() -> None:
        try:
            while True:
                line = popen_pipe.readline()
                if not line:
                    break
                decoded = prefix + line.decode("utf-8", errors="replace").rstrip("\r\n")
                if not decoded.strip() and type_str != "info":
                    continue
                lines_list.append(decoded)
                asyncio.run_coroutine_threadsafe(
                    emit_terminal_line(decoded, type_str, project_id),
                    loop,
                )
                if parser_callback:
                    clean = _ANSI_RE.sub("", decoded)
                    asyncio.run_coroutine_threadsafe(parser_callback(clean), loop)
        except Exception as e:
            try:
                asyncio.run_coroutine_threadsafe(
                    emit_terminal_line(f"Stream read error: {e}", "stderr", project_id),
                    loop,
                )
            except RuntimeError:
                pass

    thread = threading.Thread(target=reader, name=f"runtime-stream-{project_id}-{type_str}", daemon=True)
    thread.start()
    return thread


async def _stream_command_popen(
    project_id: str,
    label: str,
    args: list[str],
    cwd: str,
    env: dict,
    timeout: int,
) -> ExecuteResponse:
    """Run command via subprocess.Popen with async streaming."""
    display = " ".join(args)
    await emit_terminal_line(f"[Executor] cwd: {cwd}", "info", project_id)
    await emit_terminal_line(f"[Executor] command: {display}", "info", project_id)
    logger.info("[Executor] cwd=%s cmd=%s", cwd, display)

    try:
        popen = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        await emit_terminal_line(f"[Executor] PID {popen.pid} started", "info", project_id)

        stdout_lines = []
        stderr_lines = []

        await asyncio.wait_for(
            asyncio.gather(
                _stream_reader_sync(popen.stdout, 'stdout', project_id, stdout_lines),
                _stream_reader_sync(popen.stderr, 'stderr', project_id, stderr_lines),
            ),
            timeout=timeout,
        )

        popen.wait()
        success = (popen.returncode == 0)
        if success:
            await emit_terminal_line(f"[Executor] Exit code 0 — succeeded", "info", project_id)
        else:
            if not stderr_lines and stdout_lines:
                last = "\n".join(stdout_lines[-10:])
                await emit_terminal_line(f"[Executor] Exit code {popen.returncode} — failed", "stderr", project_id)
                await emit_terminal_line(f"[Executor] Last output (stdout):\n{last}", "stderr", project_id)
            else:
                last = "\n".join(stderr_lines[-10:]) if stderr_lines else "(no output)"
                await emit_terminal_line(f"[Executor] Exit code {popen.returncode} — failed", "stderr", project_id)
                await emit_terminal_line(f"[Executor] Last stderr:\n{last}", "stderr", project_id)

        return ExecuteResponse(
            success=success,
            command=label,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            exit_code=popen.returncode,
        )

    except asyncio.TimeoutError:
        _kill_process_tree(popen, project_id)
        err = f"Command timed out after {timeout}s"
        await emit_terminal_line(f"[Executor] {err}", "stderr", project_id)
        return ExecuteResponse(success=False, command=label, error=err, exit_code=-1)
    except Exception as e:
        import traceback
        logger.error("[Executor] Unhandled exception: %s\n%s", e, traceback.format_exc())
        return ExecuteResponse(success=False, command=label, error=repr(e), exit_code=-1)


async def stream_command_async(
    project_id: str,
    command: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> ExecuteResponse:
    """Run a whitelisted command by name (legacy)."""
    if command not in COMMAND_WHITELIST:
        return ExecuteResponse(success=False, command=command, error=f"Command {command!r} is not allowed.")
    command_str = COMMAND_WHITELIST[command]
    is_posix = sys.platform != "win32"
    args = shlex.split(command_str, posix=is_posix)
    return await stream_command_array_async(project_id, command, args, timeout)


async def stream_command_array_async(
    project_id: str,
    label: str,
    args: list[str],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    env_overrides: dict | None = None,
    run_id: str = None,
) -> ExecuteResponse:
    """Run an arbitrary command as a list of args. Streams stdout/stderr."""
    project_path = _safe_project_path(project_id, run_id)
    if not project_path.exists():
        return ExecuteResponse(success=False, command=label, error=f"Project workspace not found: {project_path}")

    if not args:
        return ExecuteResponse(success=False, command=label, error="Empty command array", exit_code=-1)

    exe = _resolve_npm_on_windows(args[0])
    if not exe:
        return ExecuteResponse(
            success=False, command=label,
            error=f"Executable not found: {args[0]!r}. Is it installed?", exit_code=-1
        )
    resolved_args = [exe] + args[1:]

    resolved_cwd = str(project_path.resolve())
    merged_env = {**os.environ, **(_MINIMAL_ENV if env_overrides is None else env_overrides)}

    return await _stream_command_popen(project_id, label, resolved_args, resolved_cwd, merged_env, timeout)


async def run_dev_server_async(project_id: str) -> ExecuteResponse:
    """Run dev server using legacy whitelist (npm run dev)."""
    command_str = COMMAND_WHITELIST["dev"]
    args = shlex.split(command_str, posix=False)
    return await run_dev_server_array_async(project_id, args)


async def run_dev_server_array_async(
    project_id: str,
    args: list[str],
    env_overrides: dict | None = None,
    port_pattern: str | None = None,
    run_id: str = None,
) -> ExecuteResponse:
    """Run dev server with arbitrary command args and intercept the port.
    Uses subprocess.Popen with async streaming (event-loop agnostic).
    Monitors both stdout AND stderr for port detection."""
    project_path = _safe_project_path(project_id, run_id)

    if not run_id:
        return ExecuteResponse(success=False, command="dev", error="Runtime isolation error: run_id is strictly required", exit_code=-1)

    server_key = project_id
    if server_key in _runtime_registry:
        old_entry = _runtime_registry[server_key]
        msg = f"[RuntimeCleanup] killing stale runtime PID {old_entry.process_pid}"
        print(msg)
        await emit_terminal_line(msg, "info", project_id)
        await _emit_runtime_lifecycle(
            "runtime.stopping",
            project_id,
            old_entry.run_id,
            f"Stopping previous runtime PID {old_entry.process_pid}",
            selected_port=old_entry.assigned_port,
            process_pid=old_entry.process_pid,
        )
        _kill_process_tree(old_entry.popen, project_id)
        
        if not await _wait_for_process_exit(old_entry.popen):
            err_msg = f"[RuntimeCleanup] Failed to kill PID {old_entry.process_pid}"
            print(err_msg)
            await emit_terminal_line(err_msg, "stderr", project_id)
            await _emit_runtime_lifecycle(
                "runtime.stop.failed",
                project_id,
                old_entry.run_id,
                err_msg,
                selected_port=old_entry.assigned_port,
                process_pid=old_entry.process_pid,
            )
            return ExecuteResponse(success=False, command="dev", error="Failed to cleanup stale runtime process", exit_code=-1)
            
        msg = "[RuntimeCleanup] verified old runtime terminated"
        print(msg)
        await emit_terminal_line(msg, "info", project_id)
        await _emit_runtime_lifecycle(
            "runtime.stopped",
            project_id,
            old_entry.run_id,
            "Previous runtime stopped",
            selected_port=old_entry.assigned_port,
            process_pid=old_entry.process_pid,
        )
            
        # Verify port release
        if old_entry.assigned_port:
            port = int(old_entry.assigned_port)
            if not await _wait_for_port_release(port):
                err_msg = f"[RuntimeCleanup] Failed to release port {port}"
                print(err_msg)
                await emit_terminal_line(err_msg, "stderr", project_id)
                await _emit_runtime_lifecycle(
                    "runtime.stop.failed",
                    project_id,
                    old_entry.run_id,
                    err_msg,
                    selected_port=port,
                    process_pid=old_entry.process_pid,
                )
                return ExecuteResponse(success=False, command="dev", error="Failed to release port", exit_code=-1)
            msg = f"[RuntimeCleanup] verified port released"
            print(msg)
            await emit_terminal_line(msg, "info", project_id)
            
            msg = f"[PortAllocator] released ports: {port}"
            print(msg)
            await emit_terminal_line(msg, "info", project_id)
            
        del _runtime_registry[server_key]

    if not args:
        return ExecuteResponse(success=False, command="dev", error="Empty command array", exit_code=-1)

    active_ports = [entry.assigned_port for entry in _runtime_registry.values() if entry.assigned_port]
    msg = f"[PortAllocator] active ports: {active_ports}"
    print(msg)
    await emit_terminal_line(msg, "info", project_id)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            allocated_port = None
            for port in range(3000, 3100):
                msg_checking = f"[PortAllocator] checking port {port}"
                print(msg_checking)
                await emit_terminal_line(msg_checking, "info", project_id)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    try:
                        s.bind(('127.0.0.1', port))
                        allocated_port = port
                        break
                    except OSError:
                        msg_unavail = f"[PortAllocator] port {port} unavailable"
                        print(msg_unavail)
                        await emit_terminal_line(msg_unavail, "warning", project_id)
                        continue
            
            if not allocated_port:
                raise RuntimeError("Could not find an available port in range 3000-3100")
                
            msg_selected = f"[PortAllocator] selected port {allocated_port}"
            print(msg_selected)
            await emit_terminal_line(msg_selected, "info", project_id)
        except RuntimeError as e:
            return ExecuteResponse(success=False, command="dev", error=str(e), exit_code=-1)

        args_with_port = [arg.replace("{port}", str(allocated_port)) for arg in args]

        exe = _resolve_npm_on_windows(args_with_port[0])
        if not exe:
            return ExecuteResponse(success=False, command="dev", error=f"Executable not found: {args_with_port[0]!r}", exit_code=-1)
        resolved_args = [exe] + args_with_port[1:]

        resolved_cwd = str(project_path.resolve())
        expected_cwd = str(_safe_project_path(project_id, run_id).resolve())
        if resolved_cwd != expected_cwd:
            return ExecuteResponse(success=False, command="dev", error=f"Runtime isolation error: expected cwd {expected_cwd}, got {resolved_cwd}", exit_code=-1)

        display = " ".join(args_with_port)
        merged_env = {**os.environ, **(_MINIMAL_ENV if env_overrides is None else env_overrides)}

        if attempt == 0:
            await emit_agent_state("starting_preview", project_id)
            await emit_terminal_line("[RuntimeRegistry] registering runtime", "info", project_id)
            
        msg_launch = f"[RuntimeLaunch] launching runtime on port {allocated_port}"
        print(msg_launch)
        await emit_terminal_line(msg_launch, "info", project_id)
        await emit_terminal_line(f"[RuntimeLaunch] project_id={project_id} run_id={run_id} cwd={resolved_cwd} port={allocated_port}", "info", project_id)
        logger.info("[RuntimeLaunch] project_id=%s run_id=%s cwd=%s cmd=%s", project_id, run_id, resolved_cwd, display)

        try:
            popen = subprocess.Popen(
                resolved_args,
                cwd=resolved_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
            )
            await _emit_runtime_lifecycle(
                "runtime.spawn.started",
                project_id,
                run_id,
                f"Runtime process started on port {allocated_port}",
                selected_port=allocated_port,
                process_pid=popen.pid,
            )
            
            entry = RuntimeEntry(
                project_id=project_id,
                run_id=run_id,
                process_pid=popen.pid,
                cwd=resolved_cwd,
                assigned_port=str(allocated_port),
                started_at=time.time(),
                runtime_type="dev_server",
                preview_url=None,
                process_status="starting",
                popen=popen
            )
            _runtime_registry[server_key] = entry
            _record_runtime_status(entry)
            
            msg_reg = f"[RuntimeRegistry] registered runtime port={allocated_port} pid={popen.pid}"
            print(msg_reg)
            await emit_terminal_line(msg_reg, "info", project_id)

            port_found = False
            selected_port = None
            compiled_pattern = re.compile(port_pattern) if port_pattern else re.compile(r'http://(?:localhost|127\.0\.0\.1):(\d+)')

            async def detect_port(line: str):
                nonlocal port_found, selected_port
                if port_found:
                    return
                match = compiled_pattern.search(line)
                if match:
                    port_found = True
                    selected_port = match.group(1)
                    url = f"http://127.0.0.1:{selected_port}"
                    entry.assigned_port = selected_port
                    entry.process_status = "starting"
                    entry.last_healthcheck = time.time()
                    _record_runtime_status(entry)
                    await _emit_runtime_lifecycle(
                        "runtime.healthcheck.started",
                        project_id,
                        run_id,
                        f"Runtime health check started on port {selected_port}",
                        selected_port=selected_port,
                        process_pid=popen.pid,
                    )
                    return
                lower = line.lower()
                if any(kw in lower for kw in ["started", "listening", "development server", "ready in"]):
                    port_found = True
                    selected_port = str(allocated_port)
                    url = f"http://127.0.0.1:{selected_port}"
                    entry.assigned_port = selected_port
                    entry.process_status = "starting"
                    entry.last_healthcheck = time.time()
                    _record_runtime_status(entry)
                    await _emit_runtime_lifecycle(
                        "runtime.healthcheck.started",
                        project_id,
                        run_id,
                        f"Runtime health check started on port {selected_port}",
                        selected_port=selected_port,
                        process_pid=popen.pid,
                    )

            prefix = "[PHPRuntime] " if "php" in exe else ""

            stdout_lines = []
            stderr_lines = []
            loop = asyncio.get_running_loop()

            _start_dev_stream_reader_thread(popen.stdout, 'stdout', project_id, stdout_lines, loop, detect_port, prefix=prefix)
            _start_dev_stream_reader_thread(popen.stderr, 'stderr', project_id, stderr_lines, loop, detect_port, prefix=prefix)

            collision = False
            for _ in range(60):
                if port_found:
                    url = f"http://127.0.0.1:{selected_port}"
                    verified, verify_error = await _wait_for_verified_runtime(url, run_id, project_id)
                    if verified:
                        entry.preview_url = url
                        entry.process_status = "running"
                        entry.last_healthcheck = time.time()
                        entry.error = None
                        _record_runtime_status(entry)
                        await _emit_runtime_lifecycle(
                            "runtime.ready",
                            project_id,
                            run_id,
                            f"Runtime verified on port {selected_port}",
                            selected_port=selected_port,
                            process_pid=popen.pid,
                        )
                        await emit_preview_ready(project_id, url, run_id=run_id, workspace=resolved_cwd)
                        await emit_terminal_line(f"[Preview] status: ready", "info", project_id)
                        await emit_agent_state("preview_ready", project_id)
                        return ExecuteResponse(success=True, command="dev", exit_code=0)

                    entry.process_status = "failed"
                    runtime_error = f"Runtime health verification failed: {verify_error}"
                    entry.last_healthcheck = time.time()
                    entry.error = runtime_error
                    _record_runtime_status(entry)
                    await emit_terminal_line(f"[Runtime] {runtime_error}", "stderr", project_id)
                    await _emit_runtime_lifecycle(
                        "runtime.healthcheck.failed",
                        project_id,
                        run_id,
                        runtime_error,
                        selected_port=selected_port,
                        process_pid=popen.pid,
                    )
                    await emit_runtime_error(
                        RuntimeErrorCode.RUNTIME_HEALTH_TIMEOUT,
                        runtime_error,
                        detail={"preview_url": url, "run_id": run_id},
                        project_id=project_id,
                        run_id=run_id,
                        source="runtime",
                    )
                    _kill_process_tree(popen, project_id)
                    if server_key in _runtime_registry:
                        del _runtime_registry[server_key]
                    return ExecuteResponse(success=False, command="dev", error=runtime_error, exit_code=-1)
                popen.poll()
                if popen.returncode is not None:
                    err_str = "".join(stderr_lines).lower()
                    if "address already in use" in err_str or "eaddrinuse" in err_str or "forbidden" in err_str:
                        collision = True
                        break
                    err = f"Dev server crashed (Exit {popen.returncode})"
                    await emit_terminal_line(f"[Runtime] {err}", "stderr", project_id)
                    entry.process_status = "failed"
                    entry.error = err
                    _record_runtime_status(entry)
                    await _emit_runtime_lifecycle(
                        "runtime.crashed",
                        project_id,
                        run_id,
                        err,
                        selected_port=allocated_port,
                        process_pid=popen.pid,
                    )
                    await emit_runtime_error(
                        RuntimeErrorCode.RUNTIME_PROCESS_CRASH,
                        err,
                        detail={"exit_code": popen.returncode},
                        project_id=project_id,
                        run_id=run_id,
                        source="runtime",
                    )
                    if server_key in _runtime_registry:
                        del _runtime_registry[server_key]
                    return ExecuteResponse(success=False, command="dev", error=err, exit_code=popen.returncode)
                await asyncio.sleep(0.5)

            if collision:
                msg_collision = "[RuntimeRetry] port collision detected"
                print(msg_collision)
                await emit_terminal_line(msg_collision, "warning", project_id)
                _kill_process_tree(popen, project_id)
                if server_key in _runtime_registry:
                    del _runtime_registry[server_key]
                continue

            _kill_process_tree(popen, project_id)
            if server_key in _runtime_registry:
                _runtime_registry[server_key].process_status = "failed"
                _runtime_registry[server_key].error = "Timed out waiting for dev server to become ready"
                _record_runtime_status(_runtime_registry[server_key])
                del _runtime_registry[server_key]
            err = "Timed out waiting for dev server to become ready"
            await emit_terminal_line(f"[Runtime] {err}", "stderr", project_id)
            await _emit_runtime_lifecycle(
                "runtime.healthcheck.failed",
                project_id,
                run_id,
                err,
                selected_port=allocated_port,
                process_pid=popen.pid,
            )
            await emit_runtime_error(
                RuntimeErrorCode.RUNTIME_HEALTH_TIMEOUT,
                err,
                detail={"port": allocated_port},
                project_id=project_id,
                run_id=run_id,
                source="runtime",
            )
            return ExecuteResponse(success=False, command="dev", error=err, exit_code=-1)

        except Exception as e:
            if server_key in _runtime_registry:
                _runtime_registry[server_key].process_status = "crashed"
                _runtime_registry[server_key].error = f"Runtime spawn failed: {e}"
                _record_runtime_status(_runtime_registry[server_key])
                del _runtime_registry[server_key]
            import traceback
            logger.error("[Runtime] Unhandled exception: %s\n%s", e, traceback.format_exc())
            await _emit_runtime_lifecycle(
                "runtime.spawn.failed",
                project_id,
                run_id,
                f"Runtime spawn failed: {e}",
            )
            return ExecuteResponse(success=False, command="dev", error=repr(e), exit_code=-1)
            
    return ExecuteResponse(success=False, command="dev", error="Max retries exceeded for port allocation", exit_code=-1)
