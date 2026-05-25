import { useState } from "react"
import { Code2 } from "lucide-react"
import PromptWorkspace from "./PromptWorkspace"
import StatusBar from "../components/StatusBar"
import RepositoryExplorer from "./RepositoryExplorer"
import PreviewPanel from "./PreviewPanel"
import { ErrorBoundary } from "../components/ErrorBoundary"
import type { WorkspaceMode } from "../layouts/WorkspaceLayout"

interface MainWorkspaceProps {
  activeView: WorkspaceMode
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
      case 'explore':
        return (
          <ErrorBoundary fallbackName="Files">
            <div className="flex flex-col h-full min-h-0">
              <div className="h-12 border-b border-border bg-[#1e1e1e] px-6 flex items-center justify-between shrink-0">
                <div>
                  <div className="text-sm text-gray-100 font-medium">Files</div>
                  <div className="text-[11px] text-gray-500">Browse generated app files for the active project.</div>
                </div>
                <label className="flex items-center gap-2 text-[12px] text-gray-400">
                  <input
                    type="checkbox"
                    checked={showInternalFiles}
                    onChange={(event) => setShowInternalFiles(event.target.checked)}
                  />
                  Show support files
                </label>
              </div>
              <RepositoryExplorer showInternalFiles={showInternalFiles} />
            </div>
          </ErrorBoundary>
        )
      case 'generate':
        return <PromptWorkspace />
      case 'edit':
        return <EditCodePlaceholder />
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

function EditCodePlaceholder() {
  return (
    <div className="flex h-full items-center justify-center bg-[#1e1e1e] p-8 text-center">
      <div className="max-w-md">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-panel">
          <Code2 className="h-5 w-5 text-blue-300" />
        </div>
        <h2 className="mt-4 text-lg font-semibold text-gray-100">Edit Code</h2>
        <p className="mt-2 text-sm text-gray-400">
          Embedded code editing will be added in a later phase.
        </p>
      </div>
    </div>
  )
}
