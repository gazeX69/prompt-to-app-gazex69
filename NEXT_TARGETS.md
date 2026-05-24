
# NEXT TARGETS

## 1. Eliminate Monolithic Fallback Generation (CRITICAL)
- **Target:** `backend/orchestrator/project_orchestrator.py`
- **Action:** Transition file generation entirely to the `PatchEngine` using the existing `TaskGraph`. Remove the raw `complete(system_prompt, user_prompt)` call.

## 2. Multi-Run Concurrent Previews (HIGH)
- **Target:** `backend/sandbox/executor.py`
- **Action:** Change `server_key` to `f"{project_id}_{run_id}"`. Allow port allocation to bind distinct ports for historical runs so users can preview multiple runs of the same project simultaneously.

## 3. Hydrate Artifact Explorer Dynamically (MEDIUM)
- **Target:** `frontend/src/stores/workspace.store.ts` and `frontend/src/panels/ArtifactExplorer.tsx`
- **Action:** Add a websocket listener or polling mechanism for `artifactSnapshots` instead of caching it permanently on load, preventing stale directory listings.

## 4. Fix Dev Server Stale Resolution (MEDIUM)
- **Target:** `backend/core/scanner/workspace_scanner.py`
- **Action:** Introduce an atomic `run_index.json` or track the latest run in SQLite instead of relying on filesystem `st_mtime` to determine `latest` symlink fallback.
