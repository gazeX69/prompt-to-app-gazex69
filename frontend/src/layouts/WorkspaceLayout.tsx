import { useState, useEffect } from "react"
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels"
import SidebarPanel from "../panels/SidebarPanel"
import MainWorkspace from "../panels/MainWorkspace"
import PreviewPanel from "../panels/PreviewPanel"
import SkillsPanel from "../panels/SkillsPanel"
import WorkspaceLoader from "../panels/WorkspaceLoader"
import { ErrorBoundary } from "../components/ErrorBoundary"
import { api } from "../services/api"
import { useSkillsStore } from "../stores/skills.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import type { SkillMeta } from "../stores/skills.store"

export default function WorkspaceLayout() {
  const [activeView, setActiveView] = useState("overview")
  const setSkills = useSkillsStore((s) => s.setSkills)
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)

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
      
      {activeView === "skills" ? (
        <div className="flex-1 h-full min-w-0">
          <ErrorBoundary fallbackName="Skills Panel">
            <SkillsPanel />
          </ErrorBoundary>
        </div>
      ) : (
        <PanelGroup orientation="horizontal" className="flex-1 h-full min-w-0">
          <Panel defaultSize={65} minSize={40} className="flex flex-col min-w-0">
            <ErrorBoundary fallbackName="Main Workspace">
              <MainWorkspace activeView={activeView} />
            </ErrorBoundary>
          </Panel>
          
          <PanelResizeHandle className="w-[1px] bg-border hover:bg-blue-500 transition-colors cursor-col-resize z-10" />
          
          <Panel defaultSize={35} minSize={25} className="flex flex-col min-w-0 bg-background">
            <ErrorBoundary fallbackName="Preview Panel">
              <PreviewPanel />
            </ErrorBoundary>
          </Panel>
        </PanelGroup>
      )}
    </div>
  )
}
