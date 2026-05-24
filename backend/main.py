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
from backend.routes.workspaces import router as workspaces_router
from backend.sockets.manager import sio, emit_terminal_line, emit_agent_state, emit_agent_activity, emit_preview_ready
from backend.core.config import settings
from backend.runtime_client.client import runtime_client
from backend.core.skills.registry import register_skill
from backend.core.skills.builtin.react_vite import ReactViteSkill
from backend.core.skills.builtin.node_backend import NodeBackendSkill
from backend.core.skills.builtin.laravel import LaravelSkill
from backend.core.skills.builtin.php_basic import PhpBasicSkill

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


def _register_builtin_skills():
    register_skill(ReactViteSkill())
    register_skill(NodeBackendSkill())
    register_skill(PhpBasicSkill())
    register_skill(LaravelSkill())
    logger.info("Built-in skills registered: react-vite, node-backend, php-basic, laravel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _register_builtin_skills()
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
fastapi_app.include_router(workspaces_router, prefix="/workspaces", tags=["Workspaces"])


# ── Skill & Scan Routes ───────────────────────────────────────────

from fastapi import Query
from backend.core.skills.registry import get_skills_metadata
from backend.core.scanner.engine import scan_project
from backend.core.router.routes import route_for_scan
from backend.models.schemas import SkillMetaSchema, ScanResultSchema, RouteResultSchema


@fastapi_app.get("/skills", response_model=list[SkillMetaSchema])
def list_skills():
    """Return all registered skill metadata."""
    return [SkillMetaSchema(
        name=m.name, type=m.type, language=m.language,
        capabilities=m.capabilities, tags=m.tags, description=m.description,
    ) for m in get_skills_metadata()]


@fastapi_app.post("/scan", response_model=ScanResultSchema)
def scan_endpoint(project_path: str = Query(..., description="Absolute path to project")):
    """Scan a project directory and return structured detection results."""
    result = scan_project(project_path)
    return ScanResultSchema(**result.to_dict())


@fastapi_app.post("/route-from-scan", response_model=RouteResultSchema)
async def route_from_scan(project_path: str = Query(..., description="Absolute path to project")):
    """Scan a project and return the routing plan."""
    scan = scan_project(project_path)
    route = await route_for_scan(scan)
    return RouteResultSchema(
        primary=route.primary_name,
        activated=route.activated_names,
        fallback_count=len(route.fallbacks),
    )

# Wrap the FastAPI application with Socket.IO
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


@fastapi_app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@fastapi_app.get("/debug")
async def debug():
    return {"status": "ok", "pid": __import__('os').getpid()}
