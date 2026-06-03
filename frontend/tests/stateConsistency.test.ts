import assert from "node:assert/strict"
import {
  getPostGenerationRefreshAction,
  getRuntimePreviewSyncAction,
  selectHydrationRunId,
  shouldAdoptRuntimeForActiveRun,
  shouldClearMissingEditorFile,
} from "../src/stateConsistency.js"

const runs = [
  { run_id: "run_failed_newer", status: "failed", active: false },
  { run_id: "run_success_active", status: "succeeded", active: true },
  { run_id: "run_success_old", status: "succeeded", active: false },
]

assert.equal(
  shouldAdoptRuntimeForActiveRun("run_B", "run_A"),
  false,
  "preview/runtime payloads for a non-active run must be rejected",
)

assert.equal(
  getRuntimePreviewSyncAction({ status: "running", url: "http://127.0.0.1:5173", run_id: "run_A" }, "run_B"),
  "clear_preview",
  "running runtime status for a different run must clear preview ownership",
)

assert.equal(
  shouldClearMissingEditorFile({
    hasSelectedFile: true,
    hasRepositorySnapshot: true,
    selectedFileExists: false,
    editorDirty: false,
  }),
  true,
  "clean editor content should clear when the selected file disappears from the tree",
)

assert.equal(
  shouldClearMissingEditorFile({
    hasSelectedFile: true,
    hasRepositorySnapshot: true,
    selectedFileExists: false,
    editorDirty: true,
  }),
  false,
  "dirty editor content should be kept as a local draft when the selected file disappears",
)

assert.equal(
  getPostGenerationRefreshAction({ status: "failed" }),
  "reload_runs_only",
  "failed generation refresh must update run status without replacing the active successful tree",
)

assert.equal(
  getPostGenerationRefreshAction({ status: "succeeded" }),
  "reload_workspace_data",
  "successful generation refresh can hydrate repository data",
)

assert.equal(
  selectHydrationRunId(runs, "run_success_active"),
  "run_success_active",
  "restored active run should be used for repository hydration",
)

assert.equal(
  selectHydrationRunId(runs, null),
  "run_success_active",
  "manifest-active successful run should beat newer failed/source-looking runs",
)

assert.equal(
  selectHydrationRunId(runs, "run_failed_newer"),
  "run_success_active",
  "failed run IDs must not become the hydration source",
)

console.log("P8-C5-H frontend state consistency helpers passed")
