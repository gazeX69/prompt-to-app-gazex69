import { useState, useEffect } from "react"
import SidebarPanel from "../panels/SidebarPanel"
import MainWorkspace from "../panels/MainWorkspace"
import WorkspaceLoader from "../panels/WorkspaceLoader"
import { ErrorBoundary } from "../components/ErrorBoundary"
import { api } from "../services/api"
import { useSkillsStore } from "../stores/skills.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { useAgentStore } from "../stores/agent.store"
import type { SkillMeta } from "../stores/skills.store"

export default function WorkspaceLayout() {
  const [activeView, setActiveView] = useState("generate")
  const setSkills = useSkillsStore((s) => s.setSkills)
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const runtimeState = useAgentStore((s) => s.runtimeState)

  useEffect(() => {
    if (runtimeState === "READY") setActiveView("preview")
  }, [runtimeState])

  useEffect(() => {
    api.fetch<SkillMeta[]>("/skills").then(setSkills).catch(() => {
      // Skills endpoint not available yet; use defaults
    })
  }, [setSkills])

  if (!activeWorkspaceId) {
    return <WorkspaceLoader />
  }

  return (
    <div className="h-screen w-screen bg-background text-foreground flex overflow-hidden font-sans selection:bg-blue-500/30">
      <ErrorBoundary fallbackName="Sidebar">
        <SidebarPanel activeView={activeView} onViewChange={setActiveView} />
      </ErrorBoundary>
      
      <div className="flex-1 h-full min-w-0">
        <ErrorBoundary fallbackName="Main Workspace">
          <MainWorkspace activeView={activeView} />
        </ErrorBoundary>
      </div>
    </div>
  )
}
