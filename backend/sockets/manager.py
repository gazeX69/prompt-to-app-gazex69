import socketio
import logging
from typing import Optional
from backend.runtime_contract import (
    ExecutionState,
    RuntimeErrorCode,
    can_transition,
    error_payload,
    normalize_error_code,
    normalize_execution_state,
)

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")
_last_state_by_project: dict[str, ExecutionState] = {}

@sio.event
async def connect(sid, environ):
    origin = environ.get('HTTP_ORIGIN', 'unknown')
    logger.info(f"[Socket] Client connected: sid={sid}, origin={origin}")

@sio.event
async def disconnect(sid):
    logger.info(f"[Socket] Client disconnected: sid={sid}")


async def emit_agent_state(state: str, project_id: Optional[str] = None):
    """
    Broadcast the state of the agent.
    Emits canonical P6.9 execution states. Legacy lowercase aliases are accepted.
    """
    normalized = normalize_execution_state(state)
    key = project_id or "__global__"
    previous = _last_state_by_project.get(key)
    _last_state_by_project[key] = normalized

    logger.info(f"Agent state changed -> {normalized.value}")
    await sio.emit('agent_state', normalized.value)
    await sio.emit('execution_event', {
        'type': 'state_transition',
        'project_id': project_id,
        'from_state': previous.value if previous else None,
        'state': normalized.value,
        'valid_transition': True if previous is None else can_transition(previous, normalized),
    })

async def emit_agent_activity(message: str, project_id: Optional[str] = None):
    """
    Broadcasts a specific file creation or action activity for the UI feed.
    """
    await sio.emit('agent_activity', {'message': message, 'project_id': project_id})

async def emit_terminal_line(text: str, type: str = 'info', project_id: Optional[str] = None):
    """
    Broadcast a terminal line.
    Type can be 'info', 'stdout', 'stderr'
    """
    await sio.emit('terminal_line', {
        'id': str(hash(text + str(type))),
        'text': text.strip(),
        'type': type
    })


async def emit_preview_ready(project_id: str, url: str, run_id: Optional[str] = None, workspace: Optional[str] = None):
    """
    Notify frontend that preview server is ready.
    """
    logger.info(f"Preview ready -> {url} (run_id={run_id})")

    await sio.emit('preview_ready', {
        'project_id': project_id,
        'url': url,
        'run_id': run_id,
        'workspace': workspace
    })
    await sio.emit('execution_event', {
        'type': 'preview_ready',
        'project_id': project_id,
        'run_id': run_id,
        'state': ExecutionState.PREVIEW_READY.value,
        'url': url,
        'workspace': workspace,
    })


async def emit_runtime_error(
    code: str | RuntimeErrorCode,
    message: str,
    detail: Optional[dict] = None,
    severity: Optional[str] = None,
    recoverable: Optional[bool] = None,
    timestamp: Optional[int | float] = None,
    suggested_action: Optional[str] = None,
    project_id: Optional[str] = None,
    run_id: Optional[str] = None,
    source: str = "runtime",
):
    """
    Emit a structured runtime failure that frontend telemetry and future planners can consume.
    """
    payload = error_payload(
        normalize_error_code(code),
        message,
        detail=detail,
        severity=severity,
        recoverable=recoverable,
        timestamp=timestamp,
        suggested_action=suggested_action,
        project_id=project_id,
        run_id=run_id,
        source=source,
    )
    await sio.emit('runtime_error', payload)
    await sio.emit('execution_event', {
        'type': 'runtime_error',
        **payload,
    })


async def emit_runtime_lifecycle_event(payload: dict):
    """
    Forward normalized runtime lifecycle events without degrading structured fields.
    """
    await sio.emit('runtime_lifecycle_event', payload)
    await sio.emit('execution_event', {
        'type': 'runtime_lifecycle_event',
        **payload,
    })
