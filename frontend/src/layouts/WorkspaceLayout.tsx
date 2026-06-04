import { useState, useEffect, useRef } from "react"
import { ArrowLeft, Loader2, Play, RefreshCw, RotateCw, Square } from "lucide-react"
import SidebarPanel from "../panels/SidebarPanel"
import MainWorkspace from "../panels/MainWorkspace"
import WorkspaceLoader from "../panels/WorkspaceLoader"
import { ErrorBoundary } from "../components/ErrorBoundary"
import { api } from "../services/api"
import { useSkillsStore } from "../stores/skills.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { useAgentStore } from "../stores/agent.store"
import { usePreviewStore } from "../stores/preview.store"
import type { SkillMeta } from "../stores/skills.store"
import type { WorkspaceMode } from "../stores/workspace.store"
import { getPostGenerationRefreshAction, getRuntimePreviewSyncAction } from "../stateConsistency"

export default function WorkspaceLayout() {
  const [runtimeAction, setRuntimeAction] = useState<"run" | "stop" | "restart" | null>(null)
  const [runtimeActionError, setRuntimeActionError] = useState<string | null>(null)
  const setSkills = useSkillsStore((s) => s.setSkills)
  
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const activeView = useWorkspaceStore((s) => s.activeWorkspaceMode)
  const setActiveWorkspaceMode = useWorkspaceStore((s) => s.setActiveWorkspaceMode)
  const activeRunId = useWorkspaceStore((s) => s.activeRunId)
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const closeWorkspace = useWorkspaceStore((s) => s.closeWorkspace)
  const editorDirty = useWorkspaceStore((s) => s.editorDirty)
  const repositorySnapshot = useWorkspaceStore((s) => s.repositorySnapshot)
  const workspaceHydrationStatus = useWorkspaceStore((s) => s.workspaceHydrationStatus)
  const ensureWorkspaceHydrated = useWorkspaceStore((s) => s.ensureWorkspaceHydrated)
  const loadWorkspaceData = useWorkspaceStore((s) => s.loadWorkspaceData)
  const loadWorkspaceRuns = useWorkspaceStore((s) => s.loadWorkspaceRuns)
  
  const runtimeState = useAgentStore((s) => s.runtimeState)
  const setAgentState = useAgentStore((s) => s.setState)
  const setRuntimeState = useAgentStore((s) => s.setRuntimeState)
  const agentState = useAgentStore((s) => s.state)
  const runtimeStatus = usePreviewStore((s) => s.runtimeStatus)
  const generationStatus = usePreviewStore((s) => s.generationStatus)
  const previewUrl = usePreviewStore((s) => s.url)
  const previewRunId = usePreviewStore((s) => s.runId)
  const setPreviewUrl = usePreviewStore((s) => s.setUrl)
  const setRuntimeStatus = usePreviewStore((s) => s.setRuntimeStatus)
  const setGenerationStatus = usePreviewStore((s) => s.setGenerationStatus)
  const clearPreview = usePreviewStore((s) => s.clear)

  const activeWorkspace = activeWorkspaceId ? workspaces[activeWorkspaceId] : null
  const normalizedRuntimeStatus = String(runtimeStatus?.status || runtimeState || "unknown").toLowerCase()
  const runtimeIsRunning = normalizedRuntimeStatus === "running" || normalizedRuntimeStatus === "ready"
  const runtimeIsBusy = ["starting", "healthcheck", "installing", "building", "preparing", "checking_ports"].includes(normalizedRuntimeStatus)
  const actionPending = runtimeAction !== null
  const postGenerationHydrationRef = useRef<string | null>(null)

  const setActiveView = (view: WorkspaceMode) => {
    setActiveWorkspaceMode(view)
  }

  const handleCloseWorkspace = () => {
    if (editorDirty && !window.confirm("Discard unsaved editor changes and return to Projects?")) {
      return
    }
    closeWorkspace()
  }

  useEffect(() => {
    api.fetch<SkillMeta[]>("/skills").then(setSkills).catch(() => {
      // Skills endpoint not available yet; use defaults
    })
  }, [setSkills])


  useEffect(() => {
    if (!activeWorkspaceId) return
    if (repositorySnapshot) return
    if (workspaceHydrationStatus === "loading") return

    void ensureWorkspaceHydrated(activeWorkspaceId)
  }, [
    activeWorkspaceId,
    repositorySnapshot,
    workspaceHydrationStatus,
    ensureWorkspaceHydrated,
  ])

  useEffect(() => {
    if (!activeWorkspaceId) return

    let cancelled = false
    const syncProjectStatus = async () => {
      try {
        const [status, generation] = await Promise.all([
          api.get<RuntimeStatusResponse>(`/runtime/${activeWorkspaceId}`, { timeout: 5000 }),
          api.get<GenerationStatusResponse>(`/generate/status/${activeWorkspaceId}`, { timeout: 5000 }).catch(() => null),
        ])
        if (cancelled) return
        setRuntimeStatus(status)
        if (generation) setGenerationStatus(generation)
        syncRuntimeStores(status, {
          activeRunId,
          previewUrl,
          previewRunId,
          setPreviewUrl,
          clearPreview,
          setRuntimeState,
        })
      } catch {
        // Runtime readback is best-effort in the workspace chrome.
      }
    }

    syncProjectStatus()
    const interval = window.setInterval(syncProjectStatus, 5000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [
    activeWorkspaceId,
    activeRunId,
    clearPreview,
    previewRunId,
    previewUrl,
    setGenerationStatus,
    setPreviewUrl,
    setRuntimeState,
    setRuntimeStatus,
  ])

  useEffect(() => {
    if (!activeWorkspaceId || !generationStatus) return
    if (generationStatus.project_id && generationStatus.project_id !== activeWorkspaceId) return

    const status = String(generationStatus.status || "").toLowerCase()
    const refreshAction = getPostGenerationRefreshAction(generationStatus)
    if (refreshAction === "ignore") return

    const generationKey = [
      activeWorkspaceId,
      generationStatus.generation_id,
      generationStatus.active_run_id,
      generationStatus.latest_run_id,
      generationStatus.run_id,
      generationStatus.runtime_run_id,
      status,
    ].filter(Boolean).join(":") || `${activeWorkspaceId}:${status}`

    if (postGenerationHydrationRef.current === generationKey) return
    postGenerationHydrationRef.current = generationKey

    if (refreshAction === "reload_workspace_data") {
      void loadWorkspaceData(activeWorkspaceId)
      return
    }

    void loadWorkspaceRuns(activeWorkspaceId)
  }, [activeWorkspaceId, generationStatus, loadWorkspaceData, loadWorkspaceRuns])

  const runRuntime = async (restart = false) => {
    if (!activeWorkspaceId || actionPending) return
    setRuntimeAction(restart ? "restart" : "run")
    setRuntimeActionError(null)
    setAgentState("STARTING_PREVIEW")
    setRuntimeState("STARTING")
    try {
      const status = await api.post<RuntimeStatusResponse>(
        `/runtime/${activeWorkspaceId}/start`,
        { restart },
        { timeout: 90000 },
      )
      setRuntimeStatus(status)
      syncRuntimeStores(status, {
        activeRunId,
        previewUrl,
        previewRunId,
        setPreviewUrl,
        clearPreview,
        setRuntimeState,
      })
      if (status.status === "running") {
        setAgentState("PREVIEW_READY")
        setActiveView("preview")
      }
      await loadWorkspaceData(activeWorkspaceId)
    } catch (error) {
      const message = error instanceof Error ? error.message : "Runtime failed to start."
      setRuntimeActionError(readableApiError(message))
      setRuntimeStatus({
        project_id: activeWorkspaceId,
        run_id: null,
        status: "failed",
        port: null,
        pid: null,
        url: null,
        started_at: null,
        last_healthcheck: Date.now(),
        error: readableApiError(message),
      })
      clearPreview()
      setAgentState("FAILED")
      setRuntimeState("FAILED")
    } finally {
      setRuntimeAction(null)
    }
  }

  const stopRuntime = async () => {
    if (!activeWorkspaceId || actionPending) return
    setRuntimeAction("stop")
    setRuntimeActionError(null)
    try {
      const status = await api.post<RuntimeStatusResponse>(`/runtime/${activeWorkspaceId}/stop`, {}, { timeout: 30000 })
      setRuntimeStatus(status)
      clearPreview()
      setRuntimeState(status.status === "failed" ? "FAILED" : "STOPPED")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Runtime failed to stop."
      setRuntimeActionError(readableApiError(message))
      setRuntimeState("FAILED")
    } finally {
      setRuntimeAction(null)
    }
  }

  if (!activeWorkspaceId) {
    return <WorkspaceLoader />
  }

  return (
    <div className="h-screen w-screen bg-background text-foreground flex flex-col overflow-hidden font-sans selection:bg-blue-500/30">
      <header className="h-16 shrink-0 border-b border-[#1a1a22] bg-[#0A0A0C]/80 backdrop-blur-md px-5 flex items-center gap-4 z-30 shadow-[0_2px_12px_rgba(0,0,0,0.4)]">
        <button
          onClick={handleCloseWorkspace}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3.5 text-xs font-semibold text-gray-300 hover:text-white transition hover:bg-white/[0.06] hover:border-white/[0.12] active:scale-95 duration-150"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Projects
        </button>

        <div className="min-w-0 flex-1 pl-2">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="truncate text-base font-bold text-gray-100 tracking-wide">
              {activeWorkspace?.name || activeWorkspaceId}
            </h1>
            <StatusBadge label={activeWorkspace?.status || "ready"} tone={statusTone(activeWorkspace?.status)} />
          </div>
          <div className="mt-1 truncate text-xs text-gray-500 font-medium">
            {activeWorkspace?.pathLabel || activeWorkspace?.path || activeWorkspaceId}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="flex items-center gap-2 border-r border-[#1a1a22] pr-3">
            <StatusBadge label={`Runtime: ${runtimeStatus?.status || runtimeState || "unknown"}`} tone={statusTone(runtimeStatus?.status || runtimeState)} />
            <StatusBadge label={`Agent: ${generationStatus?.status || readableAgentState(agentState)}`} tone={statusTone(generationStatus?.status || agentState)} />
          </div>
          <div className="flex items-center gap-2">
            <RuntimeControls
              isRunning={runtimeIsRunning}
              isBusy={runtimeIsBusy || actionPending}
              action={runtimeAction}
              onRun={() => runRuntime(false)}
              onStop={stopRuntime}
              onRestart={() => runRuntime(true)}
            />
            <button
              onClick={() => activeWorkspaceId && loadWorkspaceData(activeWorkspaceId)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] text-gray-400 hover:text-gray-100 transition hover:bg-white/[0.06] hover:border-white/[0.12] active:scale-95 duration-150"
              title="Refresh project"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      {runtimeActionError && (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-sm text-red-200">
          {runtimeActionError}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <ErrorBoundary fallbackName="Navigation">
          <SidebarPanel activeView={activeView} onViewChange={setActiveView} />
        </ErrorBoundary>

        <div className="flex-1 h-full min-w-0">
          <ErrorBoundary fallbackName="Project Workspace">
            <MainWorkspace activeView={activeView} onViewChange={setActiveView} />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}

interface RuntimeStatusResponse {
  project_id: string | null
  run_id: string | null
  status: string
  port: number | null
  pid: number | null
  url: string | null
  started_at: number | null
  last_healthcheck: number | null
  error: string | null
}

interface GenerationStatusResponse {
  project_id: string | null
  generation_id: string | null
  run_id?: string | null
  current_run_id?: string | null
  active_run_id?: string | null
  latest_run_id?: string | null
  status: string
  phase: string
  message: string
  detail: Record<string, unknown>
  created_at: number | null
  updated_at: number | null
  runtime_run_id: string | null
  runtime_url: string | null
  runtime_port: number | null
}

function RuntimeControls({
  isRunning,
  isBusy,
  action,
  onRun,
  onStop,
  onRestart,
}: {
  isRunning: boolean
  isBusy: boolean
  action: "run" | "stop" | "restart" | null
  onRun: () => void
  onStop: () => void
  onRestart: () => void
}) {
  if (isRunning) {
    return (
      <>
        <button
          onClick={onStop}
          disabled={isBusy}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50 active:scale-95 duration-150"
        >
          {action === "stop" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Square className="h-3.5 w-3.5 fill-red-300/30" />}
          Stop
        </button>
        <button
          onClick={onRestart}
          disabled={isBusy}
          className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 text-xs font-semibold text-gray-300 transition hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-50 active:scale-95 duration-150"
        >
          {action === "restart" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCw className="h-3.5 w-3.5" />}
          Restart
        </button>
      </>
    )
  }

  return (
    <button
      onClick={onRun}
      disabled={isBusy}
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-green-500/20 bg-green-500/10 px-4.5 text-xs font-semibold text-green-300 transition hover:bg-green-500/15 disabled:cursor-not-allowed disabled:opacity-50 active:scale-95 duration-150 shadow-[0_0_12px_-3px_rgba(34,197,94,0.2)]"
    >
      {action === "run" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-green-300/25" />}
      Run
    </button>
  )
}

function syncRuntimeStores(
  status: RuntimeStatusResponse,
  helpers: {
    activeRunId: string | null
    previewUrl: string | null
    previewRunId: string | null
    setPreviewUrl: (url: string | null, runId?: string | null) => void
    clearPreview: () => void
    setRuntimeState: (state: "IDLE" | "PREPARING" | "CHECKING_PORTS" | "INSTALLING" | "BUILDING" | "STARTING" | "HEALTHCHECK" | "READY" | "RUNNING" | "FAILED" | "STOPPED") => void
  },
) {
  const action = getRuntimePreviewSyncAction(status, helpers.activeRunId)
  if (action === "mount_preview" && status.url) {
    if (helpers.previewUrl !== status.url || helpers.previewRunId !== status.run_id) {
      helpers.setPreviewUrl(status.url, status.run_id)
    }
    helpers.setRuntimeState("RUNNING")
    return
  }
  if (action === "clear_preview") {
    helpers.clearPreview()
    helpers.setRuntimeState("STOPPED")
    return
  }
  if (action === "mark_failed") {
    helpers.clearPreview()
    helpers.setRuntimeState("FAILED")
    return
  }
  if (action === "mark_stopped") {
    helpers.clearPreview()
    helpers.setRuntimeState("STOPPED")
    return
  }
  if (action === "mark_starting") {
    helpers.setRuntimeState("STARTING")
  }
}

function readableApiError(message: string) {
  const match = message.match(/"detail"\s*:\s*"([^"]+)"/)
  return match?.[1] || message.replace(/^API Error \d+:\s*/, "")
}

function StatusBadge({ label, tone }: { label: string; tone: "neutral" | "good" | "warn" | "bad" | "active" }) {
  const colors = {
    neutral: "border-gray-500/20 bg-gray-500/5 text-gray-400",
    good: "border-green-500/25 bg-green-500/5 text-green-400 shadow-[0_0_12px_-4px_rgba(34,197,94,0.1)]",
    warn: "border-yellow-500/25 bg-yellow-500/5 text-yellow-400 shadow-[0_0_12px_-4px_rgba(234,179,8,0.1)]",
    bad: "border-red-500/25 bg-red-500/5 text-red-400 shadow-[0_0_12px_-4px_rgba(239,68,68,0.1)]",
    active: "border-blue-500/25 bg-blue-500/5 text-blue-400 shadow-[0_0_12px_-4px_rgba(59,130,246,0.1)]",
  }
  const dots = {
    neutral: "bg-gray-500",
    good: "bg-green-500",
    warn: "bg-yellow-500",
    bad: "bg-red-500",
    active: "bg-blue-500 animate-pulse",
  }
  return (
    <span className={`inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[10px] font-bold uppercase tracking-wider ${colors[tone]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dots[tone]}`} />
      {label}
    </span>
  )
}

function statusTone(status?: string | null): "neutral" | "good" | "warn" | "bad" | "active" {
  const normalized = String(status || "").toLowerCase()
  if (["running", "ready", "succeeded", "success", "completed", "preview_ready"].includes(normalized)) return "good"
  if (["failed", "failure"].includes(normalized)) return "bad"
  if (["generating", "accepted", "starting", "starting_preview", "building", "installing", "verifying", "repairing"].includes(normalized)) return "active"
  if (["stopped", "idle", "unknown"].includes(normalized)) return "neutral"
  return "warn"
}

function readableAgentState(state: string) {
  if (state === "IDLE") return "idle"
  if (state === "PREVIEW_READY") return "success"
  return state.toLowerCase()
}
