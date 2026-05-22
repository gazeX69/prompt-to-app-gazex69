import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from "react-resizable-panels"
import PromptWorkspace from "./PromptWorkspace"
import TerminalPanel from "./TerminalPanel"
import StatusBar from "../components/StatusBar"

export default function MainWorkspace() {
  return (
    <div className="flex flex-col h-full bg-background min-w-0">
      <PanelGroup orientation="vertical" className="flex-1 min-h-0">
        <Panel defaultSize={75} minSize={30} className="flex flex-col min-h-0">
          <PromptWorkspace />
        </Panel>
        
        <PanelResizeHandle className="h-[1px] bg-border hover:bg-blue-500 transition-colors cursor-row-resize z-10" />
        
        <Panel defaultSize={25} minSize={15} className="flex flex-col min-h-0 bg-panel">
          <TerminalPanel />
        </Panel>
      </PanelGroup>
      <StatusBar />
    </div>
  )
}
