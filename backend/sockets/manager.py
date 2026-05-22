import socketio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins="*")

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
    Valid states: idle, generating, writing, installing, building, success, failed, repairing
    """
    logger.info(f"Agent state changed -> {state}")
    await sio.emit('agent_state', state)

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


async def emit_preview_ready(project_id: str, url: str):
    """
    Notify frontend that preview server is ready.
    """
    logger.info(f"Preview ready -> {url}")

    await sio.emit('preview_ready', {
        'project_id': project_id,
        'url': url
    })
