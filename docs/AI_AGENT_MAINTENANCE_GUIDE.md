# AI AGENT MAINTENANCE GUIDE

## A. Project Identity

- **Project:** Modern TypeScript/Python Monorepo AI Agent
- **Purpose:** An intelligent orchestration layer designed to generate, validate, and auto-repair full-stack applications (React/Vite).
- **Current Phase:** Active Refactoring & Core Infrastructure Stabilization.
- **Current Architecture Maturity:** Transitional. The system operates with a separated frontend (React) and runtime (Node.js), but still heavily relies on a Python backend for core AI orchestration and WebSocket management.

---

## B. Folder Intelligence Map

- `frontend/`: The React-based IDE and UI shell. Responsible ONLY for rendering state and communicating with the backend. It contains no orchestration logic.
- `backend/`: The Python-based Central AI Core. Owns orchestration, prompting, API connections (e.g., DashScope), and WebSocket lifecycle. **(Note: This currently houses the AI logic that is intended for TS migration).**
- `packages/`: *(Targeted for Future Use)* Intended to hold shared contracts and isolated utility modules.
- `runtime/`: The Node.js Sandbox Executor. A "dumb" daemon that safely executes bash commands (npm install, build) and streams logs. Makes no AI decisions.
- `editor/`: *(Targeted for Future Use)* Intended for advanced IDE features.
- `shared/`: *(Targeted for Future Use)* Where shared types/interfaces between frontend, backend, and runtime will live to prevent contract mismatch.
- `docs/`: System documentation, maps, and AI maintenance guides.

---

## C. Critical System Dependencies

- **WebSocket Bridge (`frontend/src/sockets` <-> `backend/sockets`)**: The lifeline of the application. Do not modify event names or payloads without synchronizing both sides.
- **Orchestration Flow (`backend/orchestrator/project_orchestrator.py`)**: The strict loop of Generate -> Parse -> Write -> Install -> Build -> Auto-Repair.
- **Provider Abstraction**: Currently coupled to OpenAI-compatible SDKs in Python (`ai_service.py`).
- **Runtime Client (`backend/runtime_client`)**: Relays commands from the Python Backend to the Node Runtime.

---

## D. Safe Modification Zones

- **UI Isolated Components (`frontend/src/components/`, `frontend/src/panels/`)**: Safe to style and refactor.
- **Provider Adapters**: Safe to add new models within the existing Python service logic.
- **Settings Panels**: Safe to update UI configurations.
- **Templates (`backend/templates/`)**: Safe to add new scaffolding templates (e.g., Vue, Svelte).

---

## E. Dangerous Zones

- **Websocket Bridge**: Highly sensitive to race conditions and schema mismatches.
- **Runtime Lifecycle (`runtime/src/processes/`)**: Modifying process management can cause zombie processes on Windows (`npm.cmd`).
- **Orchestration Contracts**: Changes to payload shapes between steps will break the auto-repair loop.
- **Prisma Schema**: *(If implemented)* Modifying the DB schema requires rigorous migration testing to prevent state loss.
- **Shared Types**: Any changes must immediately be cascaded to all consumers.

---

## F. Common Failure Scenarios

| Problem | Root Cause | Fix Strategy |
| :--- | :--- | :--- |
| **Zombie Processes** | Runtime process manager failed to kill a process tree. | Audit `tree-kill` implementation in Node runtime. |
| **WebSocket Disconnects** | Unhandled exception in backend orchestrator. | Check `ERROR_LOG.md`. Ensure error states emit graceful failure messages. |
| **AI Parsing Fails** | Provider generated markdown outside expected protocol. | Enhance regex/parsing in `backend/agent/parser.py`. |
| **Contract Mismatch** | Frontend expects TS types, Backend sends Python dicts. | Standardize payloads; create shared TS interfaces. |

---

## G. AI Working Rules

- **DO NOT** perform massive sweeping refactors without an approved audit plan.
- **DO NOT** change a shared contract (WebSocket payload, API response) without updating all consumers (Frontend/Backend/Runtime) simultaneously.
- **ALWAYS** check `ARCHITECTURE_MAP.md` before altering the role of a directory.
- **ALWAYS** audit build dependencies before installing new packages. Avoid native modules that complicate cross-platform execution.
- **AVOID** circular dependencies, particularly between state stores and socket managers.
- **DOCUMENT** all unhandled edge cases found during development.

---

## H. Build & Validation Checklist

Before committing changes, ensure the following pass:
- [ ] **Typecheck**: Run `tsc --noEmit` on all TS packages.
- [ ] **Build**: Ensure `npm run build` succeeds for frontend and runtime.
- [ ] **Lint**: No ESLint or Flake8/Black warnings.
- [ ] **Runtime Health**: Ensure `http://127.0.0.1:3001/runtime/health` returns OK.
- [ ] **Backend Health**: Ensure `http://127.0.0.1:8000/health` returns OK.
- [ ] **WebSocket Validation**: Ensure terminal logs stream without latency.

---

## I. Recommended AI Workflow

1. **Read Docs**: Start with `ARCHITECTURE_MAP.md` and `AI_ROUTE_SYSTEM_MAP.md`.
2. **Audit Dependency**: Check `DEPENDENCY_RELATION_MAP.md` to gauge blast radius.
3. **Trace Feature Flow**: Follow the logic from Frontend UI -> WebSocket -> Python Backend -> Node Runtime.
4. **Make Isolated Change**: Edit files in a scoped, atomic manner.
5. **Run Validations**: Use the checklist above.
6. **Update Docs**: Log the change in `WORKLOG.md` and update maps if architecture shifted.

---

## CURRENT SYSTEM HEALTH

### Scores
- **Architecture Score:** 6/10 (Conceptually sound, but physically fragmented between Python and TypeScript).
- **Maintainability Score:** 5/10 (Lack of shared typing between Python backend and TS frontend).
- **AI-Readiness Score:** 8/10 (Excellent logging and strict boundaries make it easy for AI to assist).
- **Scalability Risk:** High (Python orchestration coupled with Node runtime introduces latency and IPC complexity).

### Technical Debt Summary
- **Dead Provider Abstraction / Architecture Drift**: The projected TypeScript `AIRoute` layer (`provider.registry.ts`, etc.) does not exist in the codebase; orchestration is heavily coupled to Python (`backend/orchestrator`).
- **Frontend/Backend Contract Mismatch**: Lack of a `shared/` directory means WebSocket payloads are manually duplicated.
- **Circular Dependency Risk**: Implicit coupling between Python Socket Manager and AI Services.

### Top Priority Stabilization Tasks
1. Establish a single source of truth for Types (e.g., OpenAPI spec or shared TS definitions).
2. Migrate or solidify the AI Orchestration Layer (Decide between standardizing the Python implementation or migrating strictly to the envisioned TypeScript `AIRoute` system).
3. Implement unified Provider Abstraction to replace direct `OpenAI` client calls in `ai_service.py`.
