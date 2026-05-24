import { useState, useEffect } from "react"
import type { WorkspaceMetadata } from "../stores/workspace.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { Folder, Terminal } from "lucide-react"
import { fetchWorkspaces } from "../api/workspace.api"

export default function WorkspaceLoader() {
  const [loading, setLoading] = useState(false)
  const [availableWorkspaces, setAvailableWorkspaces] = useState<WorkspaceMetadata[]>([])
  const [errorMsg, setErrorMsg] = useState("")
  
  const bindWorkspace = useWorkspaceStore((s) => s.bindWorkspace)
  const loadWorkspaceData = useWorkspaceStore((s) => s.loadWorkspaceData)

  useEffect(() => {
    fetchWorkspaces()
      .then((data) => setAvailableWorkspaces(data))
      .catch(() => setErrorMsg("Backend offline or unreachable."))
  }, [])

  const handleSelectWorkspace = async (ws: WorkspaceMetadata) => {
    setLoading(true)
    bindWorkspace(ws)
    await loadWorkspaceData(ws.id)
    setLoading(false)
  }

  const handleMockBind = async () => {
    // Fallback if backend is completely broken or empty
    setLoading(true)
    setTimeout(() => {
      const mockWorkspace: WorkspaceMetadata = {
        id: `ws_${Math.random().toString(36).slice(2, 9)}`,
        name: "mock_fallback_app",
        pathLabel: "/mock/path",
        ecosystem: "react-vite-ts",
        createdAt: Date.now(),
        updatedAt: Date.now(),
        runCount: 0,
        runtimeHealth: 'offline'
      }
      bindWorkspace(mockWorkspace)
      setLoading(false)
    }, 600)
  }

  return (
    <div className="flex h-screen w-screen bg-[#1e1e1e] items-center justify-center font-mono text-gray-300">
      <div className="w-[600px] border border-[#333] bg-[#252526] p-8 rounded flex flex-col items-center">
        <div className="flex items-center space-x-3 mb-6">
          <Terminal className="w-8 h-8 text-blue-500" />
          <h1 className="text-xl font-medium tracking-tight text-gray-100 font-sans">Engineering Runtime Workspace</h1>
        </div>
        
        <p className="text-gray-400 text-sm mb-8 text-center max-w-[400px]">
          Bind a repository to instantiate a persistent operational workspace.
        </p>
        
        {errorMsg && (
          <div className="mb-6 px-4 py-2 border border-red-900/50 bg-red-900/10 text-red-400 rounded text-xs">
            {errorMsg}
          </div>
        )}

        <div className="w-full space-y-3 mb-6 max-h-48 overflow-y-auto">
          {availableWorkspaces.length > 0 ? (
            availableWorkspaces.map(ws => (
              <div 
                key={ws.id} 
                onClick={() => handleSelectWorkspace(ws)}
                className={`p-3 border border-[#333] rounded cursor-pointer hover:bg-[#333] transition-colors flex justify-between items-center ${loading ? 'opacity-50 pointer-events-none' : ''}`}
              >
                <div>
                  <div className="text-sm text-gray-200 font-bold">{ws.name}</div>
                  <div className="text-xs text-gray-500 truncate max-w-xs">{ws.pathLabel}</div>
                </div>
                <div className="text-xs text-blue-400 border border-blue-900 bg-blue-900/20 px-2 py-1 rounded">
                  {ws.ecosystem}
                </div>
              </div>
            ))
          ) : !errorMsg ? (
             <div className="text-center text-xs text-gray-500 py-4">Scanning workspaces...</div>
          ) : (
             <div className="text-center text-xs text-gray-500 py-4">No workspaces found.</div>
          )}
        </div>

        <div className="flex w-full space-x-4">
          <button
            onClick={handleMockBind}
            disabled={loading}
            className="flex-1 bg-blue-600/20 hover:bg-blue-600/40 transition-colors border border-blue-500/30 rounded p-4 flex flex-col items-center justify-center space-y-2 group disabled:opacity-50"
          >
            <Folder className="w-5 h-5 text-blue-400 group-hover:text-blue-300 transition-colors" />
            <div className="text-center">
              <div className="font-medium text-blue-300 text-sm">Mock Fallback</div>
            </div>
          </button>
        </div>

        {loading && (
          <div className="mt-8 text-sm text-blue-400 animate-pulse flex items-center space-x-2">
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <span>Binding repository to runtime...</span>
          </div>
        )}
      </div>
    </div>
  )
}
