# Architecture Trace & Boundaries

Before modifying code, we trace the new strict responsibilities:

## 1. Ownership Boundaries
- **`frontend/`**: Strictly the IDE React shell. No orchestration logic, no process management.
- **`backend/` (Python)**: The Central AI Core. Owns all AI planning, multi-step reasoning, repair decisions, and orchestration state.
- **`runtime/` (Node.js)**: The sandbox executor. A dumb daemon that only spawns processes, streams logs, and manages the PTY. It makes NO decisions.
- **`workspaces/`**: Isolated output directories for generated applications. Neither frontend nor backend files live here.

## 2. WebSocket Authority
- **Python Backend**: The singular WebSocket Gateway for the `frontend/`. It broadcasts standardized frontend events (`stage_changed`, `preview_ready`, etc) and relays terminal logs.
- **Node Runtime**: Emits raw execution events (via Server-Sent Events `/runtime/events`) strictly to the Python Backend. It does NOT communicate directly with the frontend.
- **Runtime Client (`backend/runtime_client`)**: The only communication bridge. Consumes the SSE stream, normalizes events, and handles automatic reconnection to the Sandbox.

## 3. Process Authority
- **Node Runtime**: The sole owner of `execa`, `tree-kill`, and process registries. It is responsible for Windows-safe execution (`npm.cmd`) and lifecycle cleanup.
- **Python Backend**: Tells the Node Runtime *when* to spawn processes via `backend/runtime_client` (`POST /runtime/command/run`), but does not manage the OS-level PIDs itself.

## 4. Orchestration Authority
- **Python Backend**: Master orchestrator. Determines the task graph (e.g., "Step 1: Scaffold, Step 2: Install, Step 3: Start Dev Server"). Interprets raw events from Node (e.g., exit code 1) and decides if a repair loop is needed.

## 5. Preview Ownership
- **Node Runtime**: Detects port bindings (e.g., `localhost:3000`) and reports `port detected` to Python.
- **Python Backend**: Validates the preview state and emits `PREVIEW_READY` to the frontend.
- **Frontend**: Renders the iframe pointing to the generated application's dynamic port (e.g., `3000`).

### AI ORCHESTRATION LAYER

- **AI Router**: An intended capability-based routing system (`ai-router.service.ts`) designed to match requests to models dynamically, shifting reliance away from hardcoded Python wrappers.
- **Provider Abstraction**: A unified contract (`ai-provider.interface.ts`) to standardize LLM interactions across the system, enabling zero-downtime model switching.
- **Future Multi-Model Support**: Extensible registry design to support fallback models (e.g., failing over from Qwen to an alternative API if rate-limited).
- **Streaming Architecture Direction**: Transitioning towards robust server-sent events for AI tokens, ensuring real-time UI updates without blocking backend threads.
- **Local Model Strategy**: Infrastructure planned to support local LLMs (e.g., Ollama) via standard OpenAI-compatible REST endpoints for offline execution and privacy.
- **Extensibility Strategy**: Core domain logic relies strictly on abstract interfaces rather than specific SDKs, protecting the orchestrator from SDK breaking changes.

### SKILL SYSTEM (v3.0+)

- **Skill Registry** (`backend/core/skills/registry.py`): Dynamic plugin system. Skills register with metadata (name, language, capabilities, tags). Lookup by capability, language, or type.
- **Skill Interface** (`backend/core/skills/interfaces.py`): `BaseSkill` ABC with `can_handle()`, `execute()`, `get_prompt_modifiers()`, `get_detection_hints()`.
- **Built-in Skills** (`backend/core/skills/builtin/`): `react-vite`, `node-backend`, `laravel` (detection only).
- **Project Scanner** (`backend/core/scanner/engine.py`): Filesystem-based detection for 15+ frameworks, languages, and tools. Outputs structured `ProjectScanResult`.
- **Framework Router** (`backend/core/router/routes.py`): Capability-based routing. Takes scan result → matches skills → returns `RouteResult` with primary + activated skills.
- **Error Observer** (`backend/core/observer/errors.py`): Classifies runtime/build errors into 11 categories (missing dependency, port conflict, syntax error, etc.). Produces structured `Diagnostic` objects.
- **Project Patcher** (`backend/core/patcher/patch.py`): Safe modification engine. Builds `PatchPlan` from scan → applies targeted edits without destructive overwrite.
- **Integration Facade** (`backend/core/integration.py`): `prepare_project_context()` links scanner + router + skills for easy consumption by orchestrator.

### NEW REST ENDPOINTS

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/skills` | GET | List all registered skills with metadata |
| `/scan` | POST | Scan a project directory (returns `ScanResultSchema`) |
| `/route-from-scan` | POST | Scan + route skills (returns `RouteResultSchema`) |

### FLOW DIAGRAM (New Skill-Based Flow)

```
Prompt
  → Project Scan (core/scanner)
  → Framework Detection (core/scanner/detectors)
  → Skill Activation (core/skills/registry + core/router)
  → Planning
  → File Modification (core/patcher or existing orchestrator)
  → Runtime Validation
  → Error Detection (core/observer)
  → Repair Loop
```
