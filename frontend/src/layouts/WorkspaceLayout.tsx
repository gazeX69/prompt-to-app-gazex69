import { useState, useEffect } from "react"
import { ArrowLeft, RefreshCw } from "lucide-react"
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
  const setSkills = useSkillsStore((s) => s.setSkills)
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const closeWorkspace = useWorkspaceStore((s) => s.closeWorkspace)
  const loadWorkspaceData = useWorkspaceStore((s) => s.loadWorkspaceData)
  const runtimeState = useAgentStore((s) => s.runtimeState)
  const agentState = useAgentStore((s) => s.state)
  const runtimeStatus = usePreviewStore((s) => s.runtimeStatus)
  const generationStatus = usePreviewStore((s) => s.generationStatus)

  const activeWorkspace = activeWorkspaceId ? workspaces[activeWorkspaceId] : null

  useEffect(() => {
    api.fetch<SkillMeta[]>("/skills").then(setSkills).catch(() => {
      // Skills endpoint not available yet; use defaults
    })
  }, [setSkills])

  if (!activeWorkspaceId) {
    return <WorkspaceLoader />
  }

  return (
    <div className="h-screen w-screen bg-background text-foreground flex flex-col overflow-hidden font-sans selection:bg-blue-500/30">
      <header className="h-16 shrink-0 border-b border-border bg-[#151518] px-4 flex items-center gap-4">
        <button
          onClick={closeWorkspace}
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

        <div className="hidden items-center gap-2 md:flex">
          <StatusBadge label={`Runtime: ${runtimeStatus?.status || runtimeState || "unknown"}`} tone={statusTone(runtimeStatus?.status || runtimeState)} />
          <StatusBadge label={`Generation: ${generationStatus?.status || readableAgentState(agentState)}`} tone={statusTone(generationStatus?.status || agentState)} />
          <button
            onClick={() => activeWorkspaceId && loadWorkspaceData(activeWorkspaceId)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border text-gray-400 transition hover:bg-white/5 hover:text-gray-200"
            title="Refresh project"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <ErrorBoundary fallbackName="Navigation">
          <SidebarPanel activeView={activeView} onViewChange={setActiveView} />
        </ErrorBoundary>

        <div className="flex-1 h-full min-w-0">
          <ErrorBoundary fallbackName="Project Workspace">
            <MainWorkspace activeView={activeView} />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
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
