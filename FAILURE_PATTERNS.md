
# FAILURE PATTERNS

## 1. HMR Cache Invalidation Loop
**Pattern:** Frontend forces `Date.now()` on `iframeUrl` when `url` or `runId` state changes.
**Effect:** React/Vite Hot Module Replacement (HMR) state is lost completely. The entire DOM re-renders, causing a flash of blank screen and lost component state during editing.
**Root Cause:** The `PreviewPanel.tsx` forcefully invalidates the browser cache.

## 2. Monolithic Collapse Fallback
**Pattern:** The `project_orchestrator.py` runs a sophisticated `TaskGraph` generation (Shadow Mode) but then calls `complete` once to generate ALL files using `===FILE===` delimiters.
**Effect:** LLMs often fail to separate concerns for complex prompts in a single shot, resulting in `App.tsx` monoliths. The `TaskGraph` validation then correctly flags it as a "monolithic collapse detected", but it is too late.
**Root Cause:** The structural safety of the patch engine is discarded in favor of legacy monolithic text-blob generation.

## 3. Runtime Hijacking (Single Concurrency)
**Pattern:** Loading a historical run in the workspace UI and triggering a preview automatically kills the current latest run's dev server.
**Effect:** Users cannot compare runs side-by-side. The orchestration logs will show "killed stale PID" continuously if they tab back and forth.
**Root Cause:** `server_key` in `executor.py` is tied strictly to `project_id`, enforcing a global single-instance constraint per project.
