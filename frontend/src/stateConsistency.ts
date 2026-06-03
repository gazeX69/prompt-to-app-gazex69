export interface RunLike {
  run_id?: string | null
  id?: string | null
  status?: string | null
  active?: boolean
}

export interface RuntimeStatusLike {
  run_id?: string | null
  status?: string | null
  url?: string | null
}

export interface GenerationStatusLike {
  status?: string | null
}

export function isSuccessfulRunStatus(status: unknown): boolean {
  const normalized = String(status || "").toLowerCase()
  return normalized === "success" || normalized === "succeeded"
}

export function selectActiveRunId(runs: RunLike[]): string | null {
  const activeSuccessfulRun = runs.find((run) => run.active && isSuccessfulRunStatus(run.status))
  if (activeSuccessfulRun?.run_id) return activeSuccessfulRun.run_id

  const successfulRun = runs.find((run) => isSuccessfulRunStatus(run.status))
  if (successfulRun?.run_id) return successfulRun.run_id

  return null
}

export function selectHydrationRunId(runs: RunLike[], currentActiveRunId?: string | null): string | null {
  if (currentActiveRunId) {
    const currentRun = runs.find((run) => (run.run_id || run.id) === currentActiveRunId)
    if (!currentRun || isSuccessfulRunStatus(currentRun.status)) {
      return currentActiveRunId
    }
  }

  return selectActiveRunId(runs)
}

export function shouldAdoptRuntimeForActiveRun(activeRunId: string | null, payloadRunId?: string | null): boolean {
  return !activeRunId || !payloadRunId || payloadRunId === activeRunId
}

export type RuntimePreviewSyncAction = "mount_preview" | "clear_preview" | "mark_failed" | "mark_stopped" | "mark_starting" | "ignore"

export function getRuntimePreviewSyncAction(
  status: RuntimeStatusLike,
  activeRunId: string | null,
): RuntimePreviewSyncAction {
  const normalized = String(status.status || "").toLowerCase()

  if (normalized === "running" && status.url) {
    return shouldAdoptRuntimeForActiveRun(activeRunId, status.run_id) ? "mount_preview" : "clear_preview"
  }

  if (normalized === "failed") return "mark_failed"
  if (normalized === "stopped") return "mark_stopped"
  if (normalized === "starting") return "mark_starting"
  return "ignore"
}

export type PostGenerationRefreshAction = "reload_workspace_data" | "reload_runs_only" | "ignore"

export function getPostGenerationRefreshAction(status: GenerationStatusLike | null): PostGenerationRefreshAction {
  const normalized = String(status?.status || "").toLowerCase()

  if (["succeeded", "success", "completed"].includes(normalized)) return "reload_workspace_data"
  if (["failed", "failure", "runtime_failed"].includes(normalized)) return "reload_runs_only"
  return "ignore"
}

export function shouldClearMissingEditorFile(params: {
  hasSelectedFile: boolean
  hasRepositorySnapshot: boolean
  selectedFileExists: boolean
  editorDirty: boolean
}): boolean {
  return (
    params.hasSelectedFile &&
    params.hasRepositorySnapshot &&
    !params.selectedFileExists &&
    !params.editorDirty
  )
}
