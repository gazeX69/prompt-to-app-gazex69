import { useState, useEffect } from "react"
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

export type WorkspaceMode = "generate" | "explore" | "edit" | "preview"

export default function WorkspaceLayout() {
  const [activeView, setActiveView] = useState<WorkspaceMode>("generate")
  const [runtimeAction, setRuntimeAction] = useState<"run" | "stop" | "restart" | null>(null)
  const [runtimeActionError, setRuntimeActionError] = useState<string | null>(null)
  const setSkills = useSkillsStore((s) => s.setSkills)
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const closeWorkspace = useWorkspaceStore((s) => s.closeWorkspace)
  const editorDirty = useWorkspaceStore((s) => s.editorDirty)
  const loadWorkspaceData = useWorkspaceStore((s) => s.loadWorkspaceData)
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
    clearPreview,
    previewRunId,
    previewUrl,
    setGenerationStatus,
    setPreviewUrl,
    setRuntimeState,
    setRuntimeStatus,
  ])

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
      <header className="h-16 shrink-0 border-b border-border bg-[#151518] px-4 flex items-center gap-4">
        <button
          onClick={handleCloseWorkspace}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-gray-300 transition hover:bg-white/5"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Projects
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="truncate text-base font-semibold text-gray-100">
              {activeWorkspace?.name || activeWorkspaceId}
            </h1>
            <StatusBadge label={activeWorkspace?.status || "ready"} tone={statusTone(activeWorkspace?.status)} />
          </div>
          <div className="mt-0.5 truncate text-xs text-gray-500">
            {activeWorkspace?.pathLabel || activeWorkspace?.path || activeWorkspaceId}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge label={`Runtime: ${runtimeStatus?.status || runtimeState || "unknown"}`} tone={statusTone(runtimeStatus?.status || runtimeState)} />
          <StatusBadge label={`Generation: ${generationStatus?.status || readableAgentState(agentState)}`} tone={statusTone(generationStatus?.status || agentState)} />
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
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-gray-400 transition hover:bg-white/5 hover:text-gray-200"
            title="Refresh project"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
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
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-gray-300 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {action === "stop" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
          Stop
        </button>
        <button
          onClick={onRestart}
          disabled={isBusy}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm text-gray-300 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {action === "restart" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCw className="h-4 w-4" />}
          Restart
        </button>
      </>
    )
  }

  return (
    <button
      onClick={onRun}
      disabled={isBusy}
      className="inline-flex h-9 items-center gap-2 rounded-md border border-green-400/30 bg-green-500/10 px-3 text-sm text-green-200 transition hover:bg-green-500/15 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {action === "run" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
      Run
    </button>
  )
}

function syncRuntimeStores(
  status: RuntimeStatusResponse,
  helpers: {
    previewUrl: string | null
    previewRunId: string | null
    setPreviewUrl: (url: string | null, runId?: string | null) => void
    clearPreview: () => void
    setRuntimeState: (state: "IDLE" | "PREPARING" | "CHECKING_PORTS" | "INSTALLING" | "BUILDING" | "STARTING" | "HEALTHCHECK" | "READY" | "RUNNING" | "FAILED" | "STOPPED") => void
  },
) {
  const normalized = String(status.status || "").toLowerCase()
  if (normalized === "running" && status.url) {
    if (helpers.previewUrl !== status.url || helpers.previewRunId !== status.run_id) {
      helpers.setPreviewUrl(status.url, status.run_id)
    }
    helpers.setRuntimeState("RUNNING")
    return
  }
  if (normalized === "failed") {
    helpers.clearPreview()
    helpers.setRuntimeState("FAILED")
    return
  }
  if (normalized === "stopped") {
    helpers.clearPreview()
    helpers.setRuntimeState("STOPPED")
    return
  }
  if (normalized === "starting") {
    helpers.setRuntimeState("STARTING")
  }
}

function readableApiError(message: string) {
  const match = message.match(/"detail"\s*:\s*"([^"]+)"/)
  return match?.[1] || message.replace(/^API Error \d+:\s*/, "")
}

function StatusBadge({ label, tone }: { label: string; tone: "neutral" | "good" | "warn" | "bad" | "active" }) {
  const colors = {
    neutral: "border-gray-500/30 bg-gray-500/10 text-gray-300",
    good: "border-green-400/30 bg-green-500/10 text-green-300",
    warn: "border-yellow-400/30 bg-yellow-500/10 text-yellow-300",
    bad: "border-red-400/30 bg-red-500/10 text-red-300",
    active: "border-blue-400/30 bg-blue-500/10 text-blue-300",
  }
  return (
    <span className={`inline-flex h-6 items-center rounded-full border px-2.5 text-[11px] font-medium ${colors[tone]}`}>
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
