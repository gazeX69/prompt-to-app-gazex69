import { useState, useEffect } from "react"
import type { ArtifactSnapshot } from "../stores/workspace.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { fetchArtifactContent } from "../api/workspace.api"
import { Box, FileJson, ChevronRight, ChevronDown, Activity, AlertTriangle } from "lucide-react"

export default function ArtifactExplorer() {
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const artifactSnapshots = useWorkspaceStore((s) => s.artifactSnapshots)
  const activeRunId = useWorkspaceStore((s) => s.activeRunId)
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({
    root: true,
    '.orchestration': true
  })
  
  const [selectedFile, setSelectedFile] = useState<ArtifactSnapshot | null>(null)
  const [content, setContent] = useState<string>("")
  const [loadingContent, setLoadingContent] = useState<boolean>(false)
  const [contentWarning, setContentWarning] = useState<string | null>(null)

  useEffect(() => {
    if (!selectedFile || !activeWorkspaceId) return
    
    setLoadingContent(true)
    setContentWarning(null)
    setContent("")
    
    fetchArtifactContent(activeWorkspaceId, selectedFile.id, activeRunId || undefined)
      .then((res) => {
        setContent(res.content)
        if (res.error) setContentWarning(`Error loading artifact: ${res.error}`)
        else if (res.truncated) setContentWarning("File too large. Content has been truncated.")
      })
      .catch(() => {
        setContentWarning("Failed to fetch artifact content.")
      })
      .finally(() => {
        setLoadingContent(false)
      })
      
  }, [selectedFile, activeWorkspaceId])

  const toggleNode = (id: string) => {
    setExpandedNodes(prev => ({ ...prev, [id]: !prev[id] }))
  }

  if (!activeWorkspaceId) {
    return <div className="p-8 text-gray-500">No active workspace</div>
  }

  if (!artifactSnapshots || artifactSnapshots.length === 0) {
    return (
      <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono items-center justify-center p-8">
        <Activity className="w-12 h-12 text-gray-600 mb-4 animate-pulse" />
        <div className="text-gray-400">Awaiting artifact metadata...</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono overflow-hidden">
      <div className="border-b border-[#333] px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-3">
          <Box className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg text-gray-100 font-medium">Artifact Explorer</h2>
        </div>
        {activeRunId && (
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-gray-500">Run ID:</span>
            <span className="text-blue-400 font-bold">{activeRunId}</span>
          </div>
        )}
      </div>

      <div className="flex flex-1 min-h-0">
        {/* File Tree Panel */}
        <div className="w-64 border-r border-[#333] p-4 overflow-y-auto shrink-0 bg-[#252526]">
          <div className="text-xs uppercase tracking-widest text-gray-500 font-bold mb-4">Workspace Storage</div>
          
          <div className="space-y-1">
            {/* Root */}
            <div 
              className="flex items-center space-x-2 text-gray-300 cursor-pointer hover:text-gray-100 p-1 rounded hover:bg-[#333]"
              onClick={() => toggleNode('.orchestration')}
            >
              {expandedNodes['.orchestration'] ? <ChevronDown className="w-4 h-4 shrink-0" /> : <ChevronRight className="w-4 h-4 shrink-0" />}
              <span>.orchestration</span>
            </div>
            
            {/* Children */}
            {expandedNodes['.orchestration'] && (
              <div className="pl-6 space-y-1 mt-1">
                {artifactSnapshots.map((file) => (
                  <div 
                    key={file.id} 
                    className={`flex items-center justify-between cursor-pointer p-1 rounded ${selectedFile?.id === file.id ? 'bg-[#37373d] text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-[#333]'}`}
                    onClick={() => setSelectedFile(file)}
                  >
                    <div className="flex items-center space-x-2 overflow-hidden">
                      <FileJson className="w-4 h-4 text-yellow-500 shrink-0" />
                      <span className="truncate text-sm">{file.fileName}</span>
                    </div>
                    <span className="text-[10px] text-gray-500 shrink-0 ml-2">{(file.sizeBytes / 1024).toFixed(1)}kb</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Content Panel */}
        <div className="flex-1 p-6 overflow-y-auto bg-[#1e1e1e]">
          {!selectedFile ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <FileJson className="w-12 h-12 mb-4 opacity-20" />
              <p>Select an orchestration artifact to view.</p>
            </div>
          ) : (
            <div className="border border-[#333] rounded bg-[#252526] h-full flex flex-col">
              <div className="border-b border-[#333] px-4 py-2 flex items-center justify-between bg-[#1e1e1e] shrink-0">
                <div className="flex items-center space-x-2">
                  <FileJson className="w-4 h-4 text-yellow-500" />
                  <span className="text-sm font-medium text-gray-200">{selectedFile.relativePath}</span>
                </div>
                <span className="text-xs text-gray-500">{new Date(selectedFile.updatedAt).toLocaleString()}</span>
              </div>
              
              {contentWarning && (
                <div className="bg-yellow-900/20 border-b border-yellow-900/50 p-2 flex items-center text-xs text-yellow-500 shrink-0">
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  {contentWarning}
                </div>
              )}
              
              <div className="p-4 flex-1 overflow-auto relative">
                {loadingContent ? (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#252526]/80 z-10">
                    <Activity className="w-8 h-8 text-blue-500 animate-pulse" />
                  </div>
                ) : null}
                
                <pre className="text-xs text-blue-300 font-mono whitespace-pre-wrap break-all">
                  {content}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

