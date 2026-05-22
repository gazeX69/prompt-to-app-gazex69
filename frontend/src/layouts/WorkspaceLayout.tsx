import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels"
import SidebarPanel from "../panels/SidebarPanel"
import MainWorkspace from "../panels/MainWorkspace"
import PreviewPanel from "../panels/PreviewPanel"
import { ErrorBoundary } from "../components/ErrorBoundary"

export default function WorkspaceLayout() {
  return (
    <div className="h-screen w-screen bg-background text-foreground flex overflow-hidden font-sans selection:bg-blue-500/30">
      {/* Fixed Sidebar, completely removed from PanelGroup to ensure it never collapses */}
      <ErrorBoundary fallbackName="Sidebar">
        <SidebarPanel />
      </ErrorBoundary>
      
      <PanelGroup orientation="horizontal" className="flex-1 h-full min-w-0">
        <Panel defaultSize={65} minSize={40} className="flex flex-col min-w-0">
          <ErrorBoundary fallbackName="Main Workspace">
            <MainWorkspace />
          </ErrorBoundary>
        </Panel>
        
        <PanelResizeHandle className="w-[1px] bg-border hover:bg-blue-500 transition-colors cursor-col-resize z-10" />
        
        <Panel defaultSize={35} minSize={25} className="flex flex-col min-w-0 bg-background">
          <ErrorBoundary fallbackName="Preview Panel">
            <PreviewPanel />
          </ErrorBoundary>
        </Panel>
      </PanelGroup>
    </div>
  )
}
