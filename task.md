# P8-D2 Explorer File Operations

## Mission

Implement core file-management operations inside the existing Explorer only: new file, new folder, rename, delete, and move for files and folders.

## Audit Summary

- Explorer reads `repositorySnapshot.tree` from `workspace.store.ts` and selects files for `FileInspector`.
- Repository hydration uses `fetchWorkspaceTree(workspaceId, activeRunId)` and `loadRunData` keeps the frontend pinned to the active run tree.
- File reads use `GET /workspaces/{workspace_id}/file` with `path_id` and optional `run_id`.
- File saves use `PUT /workspaces/{workspace_id}/file` with the same run ownership constraint.
- Backend scanner already owns path decoding, run selection, edit-blocked segments, binary suffix protection, and run-boundary checks.

## Fixes

- [x] Modify `plan_signature.py` to support `saas`, `dashboard admin`, and complex/large CRUD apps as high complexity.
- [x] Modify `scope_analyzer.py` to include `saas` in `BROAD_APP_TYPES`.
- [x] Modify `decision_engine.py` to enforce planning (`ASK_USER_BEFORE_GENERATE`) on broad prompt keywords.
- [x] Modify `react_vite.py` (built-in skill) to add strict TypeScript/state rules to the generator prompt.
- [x] Modify `repair_loop.py` to classify and target `ts2345_nullable_state` build errors with specific correction instructions.
- [x] Modify `project_orchestrator.py` to:
  - [x] Enforce shadow mode simulation failure check.
  - [x] Save concrete patches during shadow run and reuse them during real execution.
  - [x] Terminate execution immediately on shadow run failures.
  - [x] Make monolithic collapse a hard quality gate (aborts run).
  - [x] Block single-shot monolithic fallback for medium and broad prompts.
  - [x] Persist session snapshots during real execution.
- [x] Run automated tests to verify stability.
- [x] Added Explorer controls for new file, new folder, rename, delete, and move without changing layout architecture.
- [x] Preserved editor dirty content when an open file is renamed or moved by updating only file metadata.
- [x] Clear editor state when the open file is deleted.
- [x] Added focused backend regression tests for file/folder operations, blocked paths, overwrite rejection, and run isolation.

## Validation Results

- `python -m py_compile backend/core/scanner/workspace_scanner.py backend/routes/workspaces.py test_p8d2_explorer_file_operations.py`: passed.
- `python test_p8d2_explorer_file_operations.py`: passed, 5 tests.
- `npm run build` in `frontend`: passed.

## Non-Goals

Generator, Preview, Runtime, Brain, Discovery Flow, Memory, Provider routing, Monaco internals, Project Management, Multi-Agent, Plugin System, Cloud Sync, and broad UI redesign.
