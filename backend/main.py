import sys
import asyncio

# Python 3.8+ on Windows: SelectorEventLoop does not support subprocesses.
# ProactorEventLoop is required for asyncio.create_subprocess_exec/shell.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        pass

import socketio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.generate import router as generate_router
from backend.routes.execute import router as execute_router
from backend.sockets.manager import sio, emit_terminal_line, emit_agent_state, emit_agent_activity, emit_preview_ready
from backend.core.config import settings
from backend.runtime_client.client import runtime_client

logger = logging.getLogger(__name__)
load_dotenv()


async def _bridge_runtime_event(event_type: str, payload: dict):
    """Bridge runtime SSE events to frontend WebSocket events."""
    if event_type == "COMMAND_STDOUT":
        await emit_terminal_line(payload.get("chunk", ""), "stdout", payload.get("id"))
    elif event_type == "COMMAND_STDERR":
        await emit_terminal_line(payload.get("chunk", ""), "stderr", payload.get("id"))
    elif event_type == "COMMAND_STARTED":
        await emit_terminal_line(
            f"> {payload.get('cmd', '')} {' '.join(payload.get('args', []))}",
            "info", payload.get("id")
        )
        await emit_agent_activity(f"Running: {payload.get('cmd', '')}", payload.get("id"))
    elif event_type == "COMMAND_COMPLETED":
        await emit_agent_activity(
            f"Command finished (exit {payload.get('exitCode', '?')})", payload.get("id")
        )
    elif event_type == "PREVIEW_READY":
        await emit_preview_ready(payload.get("id", ""), payload.get("url", ""))
    elif event_type == "SESSION_FAILED":
        await emit_agent_state("failed", payload.get("id"))
        await emit_agent_activity(f"Session Error: {payload.get('error', 'unknown')}", payload.get("id"))
    elif event_type == "RUNTIME_DISCONNECTED":
        await emit_agent_activity("Runtime disconnected, retrying...", None)
    elif event_type == "DEVSERVER_STARTED":
        await emit_agent_activity(f"Dev server started on port {payload.get('port', '?')}", None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_client.set_event_callback(_bridge_runtime_event)
    bg_task = asyncio.create_task(runtime_client.start_event_stream())
    logger.info("Runtime event stream bridge started")
    yield
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass


fastapi_app = FastAPI(
    title="AI Application Generator",
    description="Autonomous AI coding agent that generates, builds, and self-repairs projects.",
    version="2.0.0",
    lifespan=lifespan,
)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(generate_router, prefix="/generate", tags=["Generation"])
fastapi_app.include_router(execute_router, prefix="/execute", tags=["Execution"])

# Wrap the FastAPI application with Socket.IO
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


@fastapi_app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
