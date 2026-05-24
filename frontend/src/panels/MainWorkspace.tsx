import { useState } from "react"
import PromptWorkspace from "./PromptWorkspace"
import StatusBar from "../components/StatusBar"
import RunHistory from "./RunHistory"
import RuntimeInspector from "./RuntimeInspector"
import ArtifactExplorer from "./ArtifactExplorer"
import RepositoryExplorer from "./RepositoryExplorer"
import PreviewPanel from "./PreviewPanel"
import { ErrorBoundary } from "../components/ErrorBoundary"

interface MainWorkspaceProps {
  activeView: string
}

export default function MainWorkspace({ activeView }: MainWorkspaceProps) {
  const [showInternalFiles, setShowInternalFiles] = useState(false)

  // Determine which main view to show based on activeView
  const renderView = () => {
    switch(activeView) {
      case 'preview':
        return (
          <ErrorBoundary fallbackName="Preview Panel">
            <PreviewPanel />
          </ErrorBoundary>
        )
      case 'source':
        return (
          <ErrorBoundary fallbackName="Repository Explorer">
            <div className="flex flex-col h-full min-h-0">
              <div className="h-12 border-b border-[#333] bg-[#1e1e1e] px-6 flex items-center justify-between shrink-0">
                <div>
                  <div className="text-sm text-gray-100 font-medium">Source</div>
                  <div className="text-[11px] text-gray-500">Generated app files first. Internal AI files are hidden by default.</div>
                </div>
                <label className="flex items-center gap-2 text-[12px] text-gray-400">
                  <input
                    type="checkbox"
                    checked={showInternalFiles}
                    onChange={(event) => setShowInternalFiles(event.target.checked)}
                  />
                  Show Internal AI Files
                </label>
              </div>
              <RepositoryExplorer showInternalFiles={showInternalFiles} />
            </div>
          </ErrorBoundary>
        )
      case 'generate':
        return <PromptWorkspace />
      case 'history':
        return <RunHistory />
      case 'internal-artifacts':
        return (
          <ErrorBoundary fallbackName="Artifact Explorer">
            <ArtifactExplorer />
          </ErrorBoundary>
        )
      case 'runtime':
        return (
          <ErrorBoundary fallbackName="Runtime Inspector">
            <RuntimeInspector />
          </ErrorBoundary>
        )
      default:
        return <PromptWorkspace />
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] min-w-0">
      <div className="flex-1 min-h-0 bg-[#1e1e1e]">
        {renderView()}
      </div>
      <StatusBar />
    </div>
  )
}
