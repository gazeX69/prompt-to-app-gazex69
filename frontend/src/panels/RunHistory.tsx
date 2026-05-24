import { useState } from "react"
import { useWorkspaceStore } from "../stores/workspace.store"
import { Clock, CheckCircle, XCircle, PlayCircle, Hash, Box, FileJson, Activity } from "lucide-react"

export default function RunHistory() {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const runHistory = useWorkspaceStore(s => s.runHistory)
  const activeRunId = useWorkspaceStore(s => s.activeRunId)
  const loadRunData = useWorkspaceStore(s => s.loadRunData)
  
  const [loadingRunId, setLoadingRunId] = useState<string | null>(null)

  if (!activeWorkspaceId) {
    return <div className="p-8 text-gray-500">No active workspace</div>
  }

  const handleSelectRun = async (runId: string) => {
    if (runId === activeRunId) return
    setLoadingRunId(runId)
    await loadRunData(activeWorkspaceId, runId)
    setLoadingRunId(null)
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono overflow-y-auto">
      <div className="border-b border-[#333] px-6 py-4 flex items-center space-x-3 sticky top-0 bg-[#1e1e1e] z-10">
        <Clock className="w-5 h-5 text-blue-400" />
        <h2 className="text-lg text-gray-100 font-medium">Run History</h2>
      </div>

      <div className="p-6">
        {runHistory.length === 0 ? (
          <div className="text-sm text-gray-500 flex flex-col items-center justify-center py-20">
            <Hash className="w-12 h-12 text-[#333] mb-4" />
            <p>No runs recorded in this workspace.</p>
          </div>
        ) : (
          <div className="space-y-4 max-w-5xl">
            {runHistory.map((run) => {
              const isActive = run.run_id === activeRunId
              const isLoading = run.run_id === loadingRunId
              
              return (
                <div 
                  key={run.run_id} 
                  onClick={() => handleSelectRun(run.run_id)}
                  className={`border rounded-md p-4 flex items-start space-x-4 cursor-pointer transition-colors
                    ${isActive ? 'border-blue-500 bg-[#252526] shadow-[0_0_15px_rgba(59,130,246,0.1)]' : 'border-[#333] bg-[#252526] hover:bg-[#2a2a2b] hover:border-gray-600'}
                  `}
                >
                  <div className="mt-1 shrink-0">
                    {run.status === 'success' && <CheckCircle className="w-5 h-5 text-green-400" />}
                    {run.status === 'failure' && <XCircle className="w-5 h-5 text-red-400" />}
                    {run.status === 'running' && <PlayCircle className="w-5 h-5 text-blue-400 animate-pulse" />}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-3">
                        <span className={`text-xs font-bold font-sans tracking-wider ${isActive ? 'text-blue-400' : 'text-gray-400'}`}>
                          {run.run_id}
                        </span>
                        {isActive && <span className="text-[10px] bg-blue-900/30 text-blue-400 px-2 py-0.5 rounded border border-blue-900">ACTIVE RUN</span>}
                        {isLoading && <Activity className="w-3 h-3 text-blue-500 animate-spin" />}
                      </div>
                      <span className="text-xs text-gray-500">{new Date(run.startedAt).toLocaleString()}</span>
                    </div>
                    
                    <div className="text-sm text-gray-200 mb-4 bg-[#1e1e1e] border border-[#333] p-2 rounded truncate">
                      {run.prompt}
                    </div>
                    
                    <div className="grid grid-cols-4 gap-4 text-xs text-gray-400">
                      <div className="flex justify-between border-r border-[#333] pr-4">
                        <span className="flex items-center"><FileJson className="w-3 h-3 mr-1"/>Artifacts</span>
                        <span className="text-gray-300">{run.artifactCount || 0}</span>
                      </div>
                      <div className="flex justify-between border-r border-[#333] pr-4">
                        <span className="flex items-center"><Box className="w-3 h-3 mr-1"/>Topology</span>
                        <span className="text-gray-300">{run.topologyScore ? run.topologyScore.toFixed(1) : '-'}</span>
                      </div>
                      <div className="flex justify-between border-r border-[#333] pr-4">
                        <span>Sequencing</span>
                        <span className="text-gray-300">{run.sequencingScore ? run.sequencingScore.toFixed(1) : '-'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Duration</span>
                        <span className="text-gray-300">{(run.durationMs / 1000).toFixed(1)}s</span>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
