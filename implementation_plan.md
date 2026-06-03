# P8-D2 Implementation Plan

## Scope

Add Explorer file operations only. Keep existing workspace layout, Monaco/editor behavior, preview behavior, generation flow, and active-run hydration rules.

## Flow Trace

1. Explorer displays the active `repositorySnapshot.tree`.
2. File inspection reads content through `fetchFileContent(workspaceId, pathId, activeRunId)`.
3. Opening a file stores editor metadata/content in `workspace.store.ts`.
4. Saving writes through `saveFileContent(workspaceId, pathId, content, activeRunId)`.
5. P8-D2 mutations now use the same workspace/run/path ownership layer and then refresh the active run tree.

## Contract

1. All mutations require an active workspace and active repository run.
2. Backend resolves every operation under the requested run directory.
3. Path traversal, blocked generated/build folders, binary suffixes, root deletion, and overwrites are rejected.
4. Rename and move update the open editor file metadata when applicable while preserving content and dirty state.
5. Delete clears the open editor when the deleted path is currently selected.

## Validation Plan

1. Backend compile checks for touched Python files.
2. Focused backend regression test for create/read/edit/save, nested folders, rename, move, delete, blocked paths, overwrite rejection, and requested-run isolation.
3. Frontend `npm run build` to verify Explorer and API integration.

## Validation Results

1. `python -m py_compile backend/core/scanner/workspace_scanner.py backend/routes/workspaces.py test_p8d2_explorer_file_operations.py`: passed.
2. `python test_p8d2_explorer_file_operations.py`: passed, 5 tests.
3. `npm run build` in `frontend`: passed.

## Hard Stop

Stop after P8-D2. Do not continue to Discovery, Project Management, UI redesign, generator, runtime, preview, Monaco internals, or AI editing work.
