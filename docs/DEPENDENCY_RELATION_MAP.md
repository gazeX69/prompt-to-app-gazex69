# DEPENDENCY RELATION MAP

This document maps the coupling between modules across the entire monorepo, highlighting the boundaries and dangerous dependency chains.

## 1. Module Dependency Graph (Macro View)

```text
[ FRONTEND (React/Vite) ]  <---(WebSockets)---+
         |                                    |
  (REST API / Config)                         |
         |                                    |
         v                                    |
[ BACKEND (Python Core) ]  -------(SSE)-------+
         |                                    |
  (Provider Abstraction)                      |
         |                                    |
         v                                    v
[ AI PROVIDER (DashScope) ]         [ RUNTIME (Node.js Sandbox) ]
                                              |
                                     (OS Commands / PTY)
                                              |
                                              v
                                  [ WORKSPACE (Generated App) ]
```

---

## 2. Shared Contracts & Coupling

### Frontend/Backend API Coupling
- **State Synchronization:** The frontend's `agent.store.ts` is tightly coupled to the WebSocket payloads emitted by `backend/sockets/manager.py`. Any change to the state machine in Python must be replicated in the TypeScript store.
- **REST Contracts:** Generating a new project relies on the shape of `GenerateRequest` (Python `pydantic` schema). The frontend `api.ts` must exactly match this interface.

### Runtime/Editor Relationship
- **One-Way Command Flow:** The Editor (Frontend) cannot speak directly to the Runtime. The Frontend sends intents to the Python Backend, which determines if a shell command should be executed, and then instructs the Runtime via a REST/SSE client.
- **Preview Bridging:** The Runtime detects dynamically bound ports (e.g., `localhost:3000` for a Vite app) and relays this back up the chain to the Editor to render the iframe.

### Provider Abstraction Dependency
- **Current State:** The system is heavily coupled to the Python `ai_service.py` wrapper around DashScope/OpenAI.
- **Projected State (AIRoute):** When the TypeScript orchestration layer (`provider.registry.ts`) is fully implemented, the dependency graph will shift, pulling the AI decision-making out of Python and into a modular TypeScript layer, reducing the Python backend to a pure API gateway.

---

## 3. Dangerous Dependency Chains

⚠️ **WARNING: Modifying these chains without a system-wide audit will cause cascading failures.**

1. **The Parsing Chain:**
   `LLM Raw Output` -> `backend/agent/parser.py` -> `write_file` -> `Runtime Exec`
   *Risk:* If the LLM changes its markdown format, the parser fails, the files aren't written, and the Runtime executes against an empty directory, triggering an infinite auto-repair loop.

2. **The Socket Relay Chain:**
   `Runtime STDOUT` -> `Server-Sent Events` -> `backend/runtime_client` -> `backend/sockets/manager.py` -> `frontend/src/sockets` -> `TerminalPanel.tsx`
   *Risk:* A memory leak in the Runtime (e.g., streaming thousands of lines per second) will traverse this entire chain, potentially crashing the Python bridge and freezing the React UI.

3. **Template Scaffolding Chain:**
   `backend/templates/registry.py` -> `vite-react-ts` Base -> `npm install`
   *Risk:* Updating dependencies in the base template without testing can break the generated app's build process, meaning the AI starts every generation trying to fix a broken base template.
