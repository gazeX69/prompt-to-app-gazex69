import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels"
import PromptWorkspace from "./PromptWorkspace"
import TerminalPanel from "./TerminalPanel"
import StatusBar from "../components/StatusBar"
import WorkspaceOverview from "./WorkspaceOverview"
import RunHistory from "./RunHistory"
import RuntimeInspector from "./RuntimeInspector"
import ArtifactExplorer from "./ArtifactExplorer"
import RepositoryExplorer from "./RepositoryExplorer"

interface MainWorkspaceProps {
  activeView: string
}

export default function MainWorkspace({ activeView }: MainWorkspaceProps) {
  // Determine which main view to show based on activeView
  const renderView = () => {
    switch(activeView) {
      case 'overview':
        return <WorkspaceOverview />
      case 'repository':
        return <RepositoryExplorer />
      case 'generate':
        return <PromptWorkspace />
      case 'history':
        return <RunHistory />
      case 'artifacts':
        return <ArtifactExplorer />
      case 'inspector':
        return <RuntimeInspector />
      default:
        return <WorkspaceOverview />
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] min-w-0">
      <PanelGroup orientation="vertical" className="flex-1 min-h-0">
        <Panel defaultSize={75} minSize={30} className="flex flex-col min-h-0 bg-[#1e1e1e]">
          {renderView()}
        </Panel>
        
        <PanelResizeHandle className="h-[1px] bg-[#333] hover:bg-blue-500 transition-colors cursor-row-resize z-10" />
        
        <Panel defaultSize={25} minSize={15} className="flex flex-col min-h-0 bg-panel">
          <TerminalPanel />
        </Panel>
      </PanelGroup>
      <StatusBar />
    </div>
  )
}
