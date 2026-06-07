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
import json
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
import urllib.error
from dataclasses import dataclass
from typing import Dict, Optional, Any, Union

def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


class MockPopen:
    def __init__(self, pid: int):
        self.pid = pid
        self.returncode = None

    def poll(self) -> Optional[int]:
        if self.returncode is not None:
            return self.returncode
        if not is_pid_alive(self.pid):
            self.returncode = 0
            return self.returncode
        return None

    def kill(self) -> None:
        if self.returncode is not None:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(self.pid)], capture_output=True)
            else:
                os.kill(self.pid, 9)
            self.returncode = -9
        except OSError:
            self.returncode = 0


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
    popen: Union[subprocess.Popen, MockPopen]
    last_healthcheck: Optional[float] = None
    error: Optional[str] = None
    stdout_tail: Optional[list[str]] = None
    stderr_tail: Optional[list[str]] = None

_runtime_registry: Dict[str, RuntimeEntry] = {}
_runtime_status_snapshots: Dict[str, dict] = {}

RUNTIME_STATES = {"ALLOCATED", "STARTING", "RUNNING", "STOPPING", "STOPPED", "FAILED", "CRASHED"}
ACTIVE_RUNTIME_STATES = {"ALLOCATED", "STARTING", "RUNNING", "STOPPING"}


def _normalize_runtime_status(status: str | None) -> str:
    normalized = str(status or "").strip().upper()
    legacy = {
        "STARTING_PREVIEW": "STARTING",
        "PREVIEW_READY": "RUNNING",
        "READY": "RUNNING",
        "STOP": "STOPPED",
        "STOPPING": "STOPPING",
        "STOPPED": "STOPPED",
        "FAILED": "FAILED",
        "FAILURE": "FAILED",
        "CRASH": "CRASHED",
        "CRASHED": "CRASHED",
    }
    normalized = legacy.get(normalized, normalized)
    return normalized if normalized in RUNTIME_STATES else "STOPPED"


def _runtime_status_is(status: str | None, *expected: str) -> bool:
    expected_states = {_normalize_runtime_status(item) for item in expected}
    return _normalize_runtime_status(status) in expected_states


def _tail_lines(lines: list[str], limit: int = 20) -> list[str]:
    return [str(line) for line in lines[-limit:]]


def _attach_runtime_output_tail(entry: RuntimeEntry, stdout_lines: list[str], stderr_lines: list[str]) -> None:
    entry.stdout_tail = _tail_lines(stdout_lines)
    entry.stderr_tail = _tail_lines(stderr_lines)

def _session_file_path(project_id: str) -> Path:
    return WORKSPACE_ROOT / project_id / ".ai-agent" / "runtime_session.json"

def _save_session_status_to_disk(status: dict) -> None:
    try:
        project_id = status.get("project_id")
        if not project_id:
            return
        path = _session_file_path(str(project_id))
        if not path.parent.is_dir():
            path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "project_id": project_id,
            "run_id": status.get("run_id"),
            "pid": status.get("pid"),
            "cwd": status.get("cwd"),
            "port": str(status.get("port")) if status.get("port") is not None else None,
            "started_at": status.get("started_at"),
            "runtime_type": status.get("runtime_type") or "dev_server",
            "preview_url": status.get("url") or status.get("preview_url"),
            "status": _normalize_runtime_status(status.get("status")),
            "last_healthcheck": status.get("last_healthcheck"),
            "error": status.get("error"),
            "stdout_tail": status.get("stdout_tail") if isinstance(status.get("stdout_tail"), list) else [],
            "stderr_tail": status.get("stderr_tail") if isinstance(status.get("stderr_tail"), list) else [],
        }
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(path)
    except Exception as e:
        logger.error(f"Failed to save runtime session to disk: {e}")


def _save_session_to_disk(entry: RuntimeEntry) -> None:
    _save_session_status_to_disk({
        **_runtime_entry_to_status(entry),
        "cwd": entry.cwd,
        "runtime_type": entry.runtime_type,
    })

def _delete_session_from_disk(project_id: str) -> None:
    try:
        path = _session_file_path(project_id)
        if path.is_file():
            path.unlink()
    except Exception as e:
        logger.error(f"Failed to delete runtime session from disk for project {project_id}: {e}")

def _entry_from_session_data(project_id: str, data: dict) -> RuntimeEntry | None:
    pid = data.get("pid")
    run_id = data.get("run_id")
    port = data.get("port")
    status = _normalize_runtime_status(data.get("status"))

    if not pid or not run_id:
        return None

    if status in ACTIVE_RUNTIME_STATES and is_pid_alive(int(pid)):
        logger.info(f"Recovering active runtime session for project {project_id}, PID {pid}, port {port}")
        return RuntimeEntry(
            project_id=project_id,
            run_id=run_id,
            process_pid=int(pid),
            cwd=data.get("cwd", str((WORKSPACE_ROOT / project_id / run_id).resolve())),
            assigned_port=str(port) if port else None,
            started_at=data.get("started_at", time.time()),
            runtime_type=data.get("runtime_type", "dev_server"),
            preview_url=data.get("preview_url"),
            process_status=status,
            popen=MockPopen(int(pid)),
            last_healthcheck=data.get("last_healthcheck"),
            error=data.get("error"),
            stdout_tail=data.get("stdout_tail") if isinstance(data.get("stdout_tail"), list) else [],
            stderr_tail=data.get("stderr_tail") if isinstance(data.get("stderr_tail"), list) else [],
        )

    if status in ACTIVE_RUNTIME_STATES:
        data["status"] = "CRASHED"
        data["error"] = data.get("error") or "Runtime process is no longer alive."
        data["last_healthcheck"] = time.time()
        _save_session_status_to_disk(
            {
                "project_id": project_id,
                "run_id": run_id,
                "pid": pid,
                "cwd": data.get("cwd"),
                "port": port,
                "url": data.get("preview_url"),
                "started_at": data.get("started_at"),
                "runtime_type": data.get("runtime_type"),
                "status": "CRASHED",
                "last_healthcheck": data.get("last_healthcheck"),
                "error": data.get("error"),
                "stdout_tail": data.get("stdout_tail") if isinstance(data.get("stdout_tail"), list) else [],
                "stderr_tail": data.get("stderr_tail") if isinstance(data.get("stderr_tail"), list) else [],
            }
        )
    return None


def _status_from_session_data(project_id: str, data: dict) -> dict:
    port = data.get("port")
    return {
        "project_id": project_id,
        "run_id": data.get("run_id"),
        "status": _normalize_runtime_status(data.get("status")),
        "port": int(port) if port is not None else None,
        "pid": data.get("pid"),
        "url": data.get("preview_url"),
        "started_at": data.get("started_at"),
        "last_healthcheck": data.get("last_healthcheck"),
        "error": data.get("error"),
        "stdout_tail": data.get("stdout_tail") if isinstance(data.get("stdout_tail"), list) else [],
        "stderr_tail": data.get("stderr_tail") if isinstance(data.get("stderr_tail"), list) else [],
    }


def _read_session_from_disk(project_id: str) -> dict | None:
    session_file = _session_file_path(project_id)
    if not session_file.is_file():
        return None
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.error(f"Failed to read runtime session from {session_file}: {e}")
        return None


def recover_single_session_from_disk(project_id: str) -> None:
    """Recover a specific project's runtime session from disk if it exists and is alive."""
    data = _read_session_from_disk(project_id)
    if not data:
        return

    entry = _entry_from_session_data(project_id, data)
    if entry:
        _runtime_registry[project_id] = entry
        _runtime_status_snapshots[project_id] = _runtime_entry_to_status(entry)
        return

    _runtime_registry.pop(project_id, None)
    _runtime_status_snapshots[project_id] = _status_from_session_data(project_id, _read_session_from_disk(project_id) or data)

def recover_sessions_from_disk() -> None:
    """Scan workspaces and recover active runtime sessions."""
    if not WORKSPACE_ROOT.exists():
        return
    for project_dir in WORKSPACE_ROOT.iterdir():
        if not project_dir.is_dir():
            continue
        project_id = project_dir.name
        session_file = _session_file_path(project_id)
        if not session_file.is_file():
            continue
        try:
            recover_single_session_from_disk(project_id)
        except Exception as e:
            logger.error(f"Failed to recover session from {session_file}: {e}")

DEFAULT_TIMEOUT_SECONDS = 180
NODE_ENTRYPOINT_CHECKS = "package.json scripts.start, scripts.dev, main, index.js, server.js, process.env.PORT"


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
        "status": _normalize_runtime_status(entry.process_status),
        "port": int(entry.assigned_port) if entry.assigned_port else None,
        "pid": entry.process_pid,
        "url": entry.preview_url,
        "started_at": entry.started_at,
        "last_healthcheck": entry.last_healthcheck,
        "error": entry.error,
        "stdout_tail": _tail_lines(entry.stdout_tail or []),
        "stderr_tail": _tail_lines(entry.stderr_tail or []),
    }


def _record_runtime_status(entry: RuntimeEntry | dict) -> dict:
    status = _runtime_entry_to_status(entry) if isinstance(entry, RuntimeEntry) else entry
    status = {**status, "status": _normalize_runtime_status(status.get("status"))}
    project_id = status.get("project_id")
    if project_id:
        _runtime_status_snapshots[project_id] = status
        if isinstance(entry, RuntimeEntry):
            _save_session_to_disk(entry)
        else:
            _save_session_status_to_disk(status)
    return status


def _fail_runtime_readback(project_id: str, entry: RuntimeEntry, error: str) -> dict:
    failed_status = {
        "project_id": entry.project_id,
        "run_id": entry.run_id,
        "status": "FAILED",
        "port": int(entry.assigned_port) if entry.assigned_port else None,
        "pid": entry.process_pid,
        "url": entry.preview_url,
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

    if not _runtime_status_is(entry.process_status, "RUNNING"):
        return _runtime_entry_to_status(entry)

    if not entry.preview_url:
        return _fail_runtime_readback(project_id, entry, "Runtime marked running without a preview URL")

    try:
        status, body = _fetch_text(entry.preview_url, timeout=1.0)
        entry.last_healthcheck = time.time()
        if status == 404:
            entry.error = "Runtime responded, but preview route returned 404."
            _record_runtime_status(entry)
            return _runtime_entry_to_status(entry)
        if status >= 400:
            entry.error = f"Runtime responded with HTTP {status}."
            _record_runtime_status(entry)
            return _runtime_entry_to_status(entry)
        marker_ok, marker_error = _validate_runtime_marker(body, entry.run_id)
        if not marker_ok:
            return _fail_runtime_readback(
                project_id,
                entry,
                marker_error or "Runtime preview ownership marker is invalid.",
            )
        entry.error = marker_error
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
    if project_id not in _runtime_registry:
        recover_single_session_from_disk(project_id)
    entry = _runtime_registry.get(project_id)
    if not entry:
        return get_runtime_status(project_id), False

    status = _refresh_runtime_entry_status(project_id, entry)
    invalidated = _runtime_status_is(status.get("status"), "FAILED", "CRASHED") and _runtime_registry.get(project_id) is not entry
    if invalidated:
        await _emit_runtime_readback_failure(status, entry)
    return status, invalidated


def get_runtime_status(project_id: str | None = None) -> dict:
    if project_id:
        if project_id not in _runtime_registry:
            recover_single_session_from_disk(project_id)
        entry = _runtime_registry.get(project_id)
        if entry:
            return _refresh_runtime_entry_status(project_id, entry)
        if project_id in _runtime_status_snapshots:
            return _runtime_status_snapshots[project_id]
        return {
            "project_id": project_id,
            "run_id": None,
            "status": "STOPPED",
            "port": None,
            "pid": None,
            "url": None,
            "started_at": None,
            "last_healthcheck": None,
            "error": None,
        }

    # First attempt to recover any active runtimes on disk not yet loaded in memory registry
    try:
        recover_sessions_from_disk()
    except Exception:
        pass

    return {
        "runtimes": [_refresh_runtime_entry_status(project_id, entry) for project_id, entry in list(_runtime_registry.items())]
    }

def _kill_process_tree(popen: Union[subprocess.Popen, MockPopen], project_id: str) -> None:
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
    if project_id not in _runtime_registry:
        recover_single_session_from_disk(project_id)
    entry = _runtime_registry.get(project_id)
    if not entry:
        return get_runtime_status(project_id)

    entry.process_status = "STOPPING"
    _record_runtime_status(entry)
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
        entry.process_status = "FAILED"
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
        "status": "STOPPED",
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
    if project_id not in _runtime_registry:
        recover_single_session_from_disk(project_id)
    if project_id in _runtime_registry:
        await stop_runtime(project_id)

    status = {
        "project_id": project_id,
        "run_id": run_id,
        "status": "FAILED",
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
    try:
        res = urllib.request.urlopen(url, timeout=timeout)
        body = res.read().decode("utf-8", errors="replace")
        return int(getattr(res, "status", 200)), body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body


def _is_route_not_found_status(status: int) -> bool:
    return status == 404


def _extract_run_marker(body: str) -> str | None:
    patterns = [
        r'<meta\s+name=["\']ai-run-id["\']\s+content=["\']([^"\']+)["\']',
        r'data-run-id=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return match.group(1)
    return None


def _validate_runtime_marker(body: str, run_id: str) -> tuple[bool, str | None]:
    marker = _extract_run_marker(body)
    if not marker:
        return True, "Runtime process is reachable, but preview ownership marker is missing."
    if marker != run_id:
        return False, f"Runtime preview belongs to a different run. Expected {run_id}, got {marker}."
    return True, None


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
            if _is_route_not_found_status(status):
                return True, "Runtime responded, but preview route returned 404."
            if status >= 400:
                last_error = f"HTTP {status}"
            else:
                marker_ok, marker_error = _validate_runtime_marker(body, run_id)
                if marker_ok:
                    return True, marker_error
                last_error = marker_error
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


def _read_package_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid package.json: {exc}") from exc


def _strip_cli_options(tokens: list[str], options_with_values: set[str], flags: set[str]) -> list[str]:
    stripped: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue

        option_name = token.split("=", 1)[0]
        if option_name in options_with_values:
            if "=" not in token:
                skip_next = True
            continue
        if option_name in flags:
            continue
        stripped.append(token)
    return stripped


def _split_package_script(script: str) -> list[str]:
    try:
        return shlex.split(script, posix=sys.platform != "win32")
    except ValueError:
        return []


def _npm_run_script_name(args: list[str]) -> str | None:
    if len(args) < 3:
        return None
    if Path(str(args[0])).name.lower() not in {"npm", "npm.cmd"}:
        return None
    if str(args[1]).lower() != "run":
        return None
    script_name = str(args[2])
    return script_name if script_name else None


def _args_after_npm_double_dash(args: list[str]) -> list[str]:
    try:
        separator_index = args.index("--")
    except ValueError:
        return []
    return [str(item) for item in args[separator_index + 1:]]


def _normalize_vite_dev_command_args(run_path: Path, args: list[str], allocated_port: int) -> list[str]:
    """Build one effective Vite command with one port, without editing package.json."""
    script_name = _npm_run_script_name(args)
    if not script_name:
        return args

    if not (run_path / "package.json").is_file():
        return args
    package = _read_package_json(run_path / "package.json")
    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    script = scripts.get(script_name)
    if not isinstance(script, str):
        return args

    script_tokens = _split_package_script(script)
    if not script_tokens:
        return args

    executable = Path(script_tokens[0]).name.lower()
    if executable not in {"vite", "vite.cmd"}:
        return args

    strip_value_options = {"--port", "-p", "--host"}
    strip_flags = {"--strictPort"}
    script_options = _strip_cli_options(script_tokens[1:], strip_value_options, strip_flags)
    extra_options = _strip_cli_options(_args_after_npm_double_dash(args), strip_value_options, strip_flags)
    normalized = [
        "npm",
        "exec",
        "vite",
        "--",
        *script_options,
        *extra_options,
        "--host",
        "127.0.0.1",
        "--port",
        str(allocated_port),
        "--strictPort",
    ]
    return normalized


def _extract_script_entrypoint(script: str) -> str | None:
    for match in re.finditer(r"(?P<entry>[\w./@-]+\.(?:mjs|cjs|js))", script):
        entry = match.group("entry").replace("\\", "/").lstrip("./")
        if entry.startswith("node_modules/"):
            continue
        return entry
    return None


def _entry_exists(run_path: Path, entry: str | None) -> bool:
    if not entry:
        return False
    relative = Path(entry)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    return (run_path / relative).is_file()


def resolve_node_runtime_entrypoint(run_path: Path) -> dict:
    """Resolve a strict Node backend entrypoint from package metadata or known files."""
    if not run_path.exists() or not run_path.is_dir():
        return {
            "ok": False,
            "error": "Generated run folder not found.",
            "checked": NODE_ENTRYPOINT_CHECKS,
        }

    package_path = run_path / "package.json"
    if package_path.is_file():
        package = _read_package_json(package_path)
        scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
        for script_name in ["start", "dev"]:
            script = scripts.get(script_name)
            if isinstance(script, str):
                entry = _extract_script_entrypoint(script)
                if _entry_exists(run_path, entry):
                    return {
                        "ok": True,
                        "source": f"scripts.{script_name}",
                        "entry": entry,
                        "command": ["npm", "run", script_name],
                        "checked": NODE_ENTRYPOINT_CHECKS,
                    }

        main_entry = package.get("main")
        if isinstance(main_entry, str):
            main_entry = main_entry.replace("\\", "/").lstrip("./")
            if _entry_exists(run_path, main_entry):
                return {
                    "ok": True,
                    "source": "main",
                    "entry": main_entry,
                    "command": ["node", main_entry],
                    "checked": NODE_ENTRYPOINT_CHECKS,
                }

    for entry in ["index.js", "server.js"]:
        if (run_path / entry).is_file():
            return {
                "ok": True,
                "source": entry,
                "entry": entry,
                "command": ["node", entry],
                "checked": NODE_ENTRYPOINT_CHECKS,
            }

    return {
        "ok": False,
        "error": f"No supported Node entrypoint found. Checked {NODE_ENTRYPOINT_CHECKS}.",
        "checked": NODE_ENTRYPOINT_CHECKS,
    }


def _node_entry_uses_env_port(run_path: Path, entry: str | None) -> bool:
    if not entry:
        return False
    entry_path = run_path / entry
    if not entry_path.is_file():
        return False
    try:
        text = entry_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return "process.env.PORT" in text or "process.env['PORT']" in text or 'process.env["PORT"]' in text


def validate_node_runtime_contract(project_id: str, run_id: str = None) -> str | None:
    run_path = _safe_project_path(project_id, run_id)
    result = resolve_node_runtime_entrypoint(run_path)
    if not result.get("ok"):
        return str(result.get("error"))
    if not _node_entry_uses_env_port(run_path, result.get("entry")):
        return "Node runtime contract violation: server entrypoint must listen on process.env.PORT."
    return None


def resolve_node_runtime_command(project_id: str, run_id: str = None) -> list[str]:
    run_path = _safe_project_path(project_id, run_id)
    result = resolve_node_runtime_entrypoint(run_path)
    if not result.get("ok"):
        raise ValueError(str(result.get("error")))
    command = result.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError(str(result.get("error") or "No supported Node runtime command found."))
    return [str(item) for item in command]


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
                if len(lines_list) > 100:
                    del lines_list[:-100]
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
    if server_key not in _runtime_registry:
        recover_single_session_from_disk(server_key)
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
            old_entry.process_status = "FAILED"
            old_entry.error = err_msg
            _record_runtime_status(old_entry)
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
        old_entry.process_status = "STOPPED"
        old_entry.error = None
        _record_runtime_status(old_entry)
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
                old_entry.process_status = "FAILED"
                old_entry.error = err_msg
                _record_runtime_status(old_entry)
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
            
        if _runtime_registry.get(server_key) is old_entry:
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
        args_with_port = _normalize_vite_dev_command_args(project_path, args_with_port, allocated_port)

        exe = _resolve_npm_on_windows(args_with_port[0])
        if not exe:
            return ExecuteResponse(success=False, command="dev", error=f"Executable not found: {args_with_port[0]!r}", exit_code=-1)
        resolved_args = [exe] + args_with_port[1:]

        resolved_project_path = project_path.resolve()
        resolved_cwd = str(resolved_project_path)

        project_root = _safe_project_path(project_id, None).resolve()
        try:
            resolved_project_path.relative_to(project_root)
        except ValueError:
            return ExecuteResponse(
                success=False,
                command="dev",
                error=f"Runtime isolation error: cwd {resolved_cwd} is outside project root {project_root}",
                exit_code=-1,
            )

        display = " ".join(args_with_port)
        merged_env = {**os.environ, **(_MINIMAL_ENV if env_overrides is None else env_overrides)}
        merged_env["PORT"] = str(allocated_port)

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
                process_status="ALLOCATED",
                popen=popen
            )
            _runtime_registry[server_key] = entry
            _record_runtime_status(entry)
            entry.process_status = "STARTING"
            _record_runtime_status(entry)
            
            msg_reg = f"[RuntimeRegistry] registered runtime port={allocated_port} pid={popen.pid}"
            print(msg_reg)
            await emit_terminal_line(msg_reg, "info", project_id)

            port_found = False
            selected_port = None
            contract_violation = None
            compiled_pattern = re.compile(port_pattern) if port_pattern else re.compile(r'http://(?:localhost|127\.0\.0\.1):(\d+)')

            async def detect_port(line: str):
                nonlocal port_found, selected_port, contract_violation
                if port_found:
                    return
                match = compiled_pattern.search(line)
                if match:
                    port_found = True
                    selected_port = match.group(1)
                    if str(selected_port) != str(allocated_port):
                        contract_violation = (
                            f"CONTRACT VIOLATION: allocated port {allocated_port}, "
                            f"runtime reported port {selected_port}"
                        )
                        return
                    url = f"http://127.0.0.1:{selected_port}"
                    entry.assigned_port = selected_port
                    entry.process_status = "STARTING"
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
                    entry.process_status = "STARTING"
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
            entry.stdout_tail = stdout_lines
            entry.stderr_tail = stderr_lines
            loop = asyncio.get_running_loop()

            _start_dev_stream_reader_thread(popen.stdout, 'stdout', project_id, stdout_lines, loop, detect_port, prefix=prefix)
            _start_dev_stream_reader_thread(popen.stderr, 'stderr', project_id, stderr_lines, loop, detect_port, prefix=prefix)

            collision = False
            for _ in range(60):
                if port_found:
                    url = f"http://127.0.0.1:{selected_port}"
                    if contract_violation:
                        entry.process_status = "FAILED"
                        entry.last_healthcheck = time.time()
                        entry.error = contract_violation
                        _attach_runtime_output_tail(entry, stdout_lines, stderr_lines)
                        _record_runtime_status(entry)
                        await emit_terminal_line(f"[Runtime] {contract_violation}", "stderr", project_id)
                        await _emit_runtime_lifecycle(
                            "runtime.healthcheck.failed",
                            project_id,
                            run_id,
                            contract_violation,
                            selected_port=allocated_port,
                            process_pid=popen.pid,
                        )
                        await emit_runtime_error(
                            RuntimeErrorCode.RUNTIME_HEALTH_TIMEOUT,
                            contract_violation,
                            detail={"allocated_port": allocated_port, "runtime_port": selected_port},
                            project_id=project_id,
                            run_id=run_id,
                            source="runtime",
                        )
                        _kill_process_tree(popen, project_id)
                        if server_key in _runtime_registry:
                            del _runtime_registry[server_key]
                        return ExecuteResponse(success=False, command="dev", error=contract_violation, exit_code=-1)
                    verified, verify_error = await _wait_for_verified_runtime(url, run_id, project_id)
                    if verified:
                        entry.preview_url = url
                        entry.process_status = "RUNNING"
                        entry.last_healthcheck = time.time()
                        entry.error = verify_error
                        _record_runtime_status(entry)
                        ready_message = (
                            f"Runtime reachable on port {selected_port}; preview route returned 404"
                            if verify_error
                            else f"Runtime verified on port {selected_port}"
                        )
                        await _emit_runtime_lifecycle(
                            "runtime.ready",
                            project_id,
                            run_id,
                            ready_message,
                            selected_port=selected_port,
                            process_pid=popen.pid,
                        )
                        await emit_preview_ready(project_id, url, run_id=run_id, workspace=resolved_cwd)
                        if verify_error:
                            await emit_terminal_line(f"[Preview] {verify_error}", "warning", project_id)
                        else:
                            await emit_terminal_line(f"[Preview] status: ready", "info", project_id)
                        await emit_agent_state("preview_ready", project_id)
                        return ExecuteResponse(success=True, command="dev", exit_code=0)

                    entry.process_status = "FAILED"
                    runtime_error = f"Runtime health verification failed: {verify_error}"
                    entry.last_healthcheck = time.time()
                    entry.error = runtime_error
                    _attach_runtime_output_tail(entry, stdout_lines, stderr_lines)
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
                    entry.process_status = "CRASHED"
                    entry.error = err
                    _attach_runtime_output_tail(entry, stdout_lines, stderr_lines)
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
                entry.process_status = "FAILED"
                entry.error = msg_collision
                _attach_runtime_output_tail(entry, stdout_lines, stderr_lines)
                _record_runtime_status(entry)
                _kill_process_tree(popen, project_id)
                if server_key in _runtime_registry:
                    del _runtime_registry[server_key]
                continue

            _kill_process_tree(popen, project_id)
            if server_key in _runtime_registry:
                _runtime_registry[server_key].process_status = "FAILED"
                _runtime_registry[server_key].error = "Timed out waiting for dev server to become ready"
                _attach_runtime_output_tail(_runtime_registry[server_key], stdout_lines, stderr_lines)
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
                _runtime_registry[server_key].process_status = "CRASHED"
                _runtime_registry[server_key].error = f"Runtime spawn failed: {e}"
                try:
                    _attach_runtime_output_tail(_runtime_registry[server_key], stdout_lines, stderr_lines)
                except NameError:
                    pass
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


# Recover any existing active sessions on module load
try:
    recover_sessions_from_disk()
except Exception as _e:
    logger.error(f"Error recovering sessions on module load: {_e}")
