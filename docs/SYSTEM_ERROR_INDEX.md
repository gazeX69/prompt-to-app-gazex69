# SYSTEM ERROR INDEX

This knowledgebase serves as the central troubleshooting guide for the AI Agent infrastructure.

---

## A. Frontend Errors

### 1. "Cannot connect to AI Core" (White screen / Infinite loader)
- **Symptom:** UI fails to initialize or shows an offline indicator.
- **Probable Cause:** Vite development server is running, but the Python backend (`uvicorn`) is not active or responding.
- **Affected Files:** `frontend/src/services/api.ts`, `frontend/src/App.tsx`.
- **Debug Steps:** Check network tab for CORS errors or 502 Bad Gateway. Verify `backend/main.py` is running.
- **Safe Fix Strategy:** Ensure `DASHSCOPE_API_KEY` is set in `.env` and restart the backend server. Do not modify CORS unless explicitly needed.

---

## B. Backend Errors

### 1. "ParseError: Malformed AI Response"
- **Symptom:** AI generates text, but it fails to write files to the workspace.
- **Probable Cause:** LLM hallucinated outside the strict file generation protocol (e.g., missing codeblocks or wrong format).
- **Affected Files:** `backend/agent/parser.py`, `backend/orchestrator/project_orchestrator.py`.
- **Debug Steps:** Check `ERROR_LOG.md` in the generated workspace for the raw output.
- **Safe Fix Strategy:** Adjust system prompts in `app/prompts/templates.py` to enforce stricter formatting rather than writing complex regex fallbacks.

---

## C. Runtime Errors

### 1. "Zombie Process / EADDRINUSE"
- **Symptom:** Port 3000 is blocked on subsequent generations.
- **Probable Cause:** Node runtime failed to terminate the previous React dev server tree.
- **Affected Files:** `runtime/src/processes/RuntimeProcessManager.ts`.
- **Debug Steps:** Use Task Manager or `netstat -ano | findstr 3000` to find the rogue PID.
- **Safe Fix Strategy:** Improve `tree-kill` logic for Windows specifically (managing `.cmd` processes).

---

## D. AI Routing Errors

### 1. "Architecture Drift: TypeScript Provider Abstraction Missing" *(Real Audit Finding)*
- **Symptom:** Searching for `provider.registry.ts` or `ai-router.service.ts` yields no results.
- **Probable Cause:** The system currently relies on Python (`backend/services/ai_service.py`) for AI orchestration, conflicting with the envisioned TypeScript `AIRoute` design.
- **Affected Files:** `backend/services/ai_service.py`, `backend/orchestrator/project_orchestrator.py`.
- **Debug Steps:** Cross-reference `ARCHITECTURE_MAP.md` with the physical file tree.
- **Safe Fix Strategy:** Document the current Python reliance. Plan a migration phase to port `ai_service.py` to the TS Runtime, or formally adopt Python as the final orchestration layer.

---

## E. Prisma Errors

*(Note: Prisma is planned but currently not fully integrated in the target state. These apply when the DB layer is activated).*

### 1. "Schema Validation Failed"
- **Symptom:** Backend crashes on startup or fails to save generation logs.
- **Probable Cause:** Prisma client is out of sync with the database schema.
- **Affected Files:** `backend/prisma/schema.prisma` (Projected).
- **Debug Steps:** Run `npx prisma migrate status`.
- **Safe Fix Strategy:** Run `npx prisma generate` to rebuild the local client. Never manually edit the SQLite/Postgres DB.

---

## F. Websocket Errors

### 1. "Terminal Log Latency / Dropped Events"
- **Symptom:** Frontend terminal stutters or misses build logs.
- **Probable Cause:** High throughput of STDOUT from the Node runtime overwhelms the Python WebSocket bridge.
- **Affected Files:** `backend/sockets/manager.py`, `frontend/src/sockets/socketManager.ts`.
- **Debug Steps:** Monitor the SSE stream from `runtime` to `backend`.
- **Safe Fix Strategy:** Implement a batching mechanism in `backend/runtime_client` to send logs in chunks rather than line-by-line.

---

## G. Build Errors

### 1. "NPM Install Failed" in Generated Workspace
- **Symptom:** Auto-repair triggers immediately after the install phase.
- **Probable Cause:** LLM hallucinated a non-existent npm package or mismatched versions in `package.json`.
- **Affected Files:** Generated `package.json`, `backend/orchestrator/project_orchestrator.py`.
- **Debug Steps:** Read the `STDERR` output in the workspace's `ERROR_LOG.md`.
- **Safe Fix Strategy:** The orchestrator's auto-repair loop should feed the exact `npm ERR!` string back to the LLM to fix the `package.json`. If it fails permanently, update the base templates in `backend/templates/`.
