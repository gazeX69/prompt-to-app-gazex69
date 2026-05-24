import { useState } from "react"
import type { RepositoryFileNode } from "../stores/workspace.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { Folder, ChevronRight, ChevronDown, FileCode } from "lucide-react"
import FileInspector from "./FileInspector"

export default function RepositoryExplorer() {
  const repositorySnapshot = useWorkspaceStore(s => s.repositorySnapshot)
  const activeRunId = useWorkspaceStore(s => s.activeRunId)
  const [selectedFile, setSelectedFile] = useState<RepositoryFileNode | null>(null)

  if (!repositorySnapshot) {
    return <div className="p-8 text-gray-500">Awaiting repository hydration...</div>
  }

  // Helper to find a file node by path
  const findNodeByPath = (nodes: RepositoryFileNode[], path: string): RepositoryFileNode | null => {
    for (const node of nodes) {
      if (node.path === path) return node
      if (node.children) {
        const found = findNodeByPath(node.children, path)
        if (found) return found
      }
    }
    return null
  }

  const handleSymbolClick = (filePath: string) => {
    const node = findNodeByPath(repositorySnapshot.tree, filePath)
    if (node) setSelectedFile(node)
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono overflow-hidden">
      <div className="border-b border-[#333] px-6 py-4 flex items-center justify-between shrink-0 bg-[#1e1e1e]">
        <div className="flex items-center space-x-3">
          <Folder className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg text-gray-100 font-medium">Repository Explorer</h2>
        </div>
        <div className="flex items-center space-x-4">
          {activeRunId && (
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-gray-500">Run ID:</span>
              <span className="text-blue-400 font-bold">{activeRunId}</span>
            </div>
          )}
          <div className="text-xs text-gray-500 border-l border-[#333] pl-4">
            {repositorySnapshot.totalFiles} files • {repositorySnapshot.ecosystem}
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left: File Tree */}
        <div className="w-1/2 border-r border-[#333] p-4 overflow-y-auto bg-[#252526]">
          <div className="text-xs uppercase tracking-widest text-gray-500 font-bold mb-4">Workspace Files</div>
          <div className="space-y-1">
            {repositorySnapshot.tree.map((node, i) => (
              <FileTreeNode key={i} node={node} onSelect={setSelectedFile} selectedPath={selectedFile?.path} />
            ))}
          </div>
        </div>

        {/* Right: Metadata Inspector / File Inspector */}
        <div className="flex-1 overflow-hidden bg-[#1e1e1e]">
          {!selectedFile ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <FileCode className="w-12 h-12 mb-4 opacity-20" />
              <p>Select a file to inspect content and symbols.</p>
              <p className="text-xs mt-2 opacity-50">(Read-only inspection phase)</p>
            </div>
          ) : selectedFile.type === 'directory' ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Folder className="w-12 h-12 mb-4 opacity-20 text-blue-400" />
              <p>Directory selected: {selectedFile.name}</p>
            </div>
          ) : (
            <FileInspector file={selectedFile} onSymbolClick={handleSymbolClick} />
          )}
        </div>
      </div>
    </div>
  )
}

function FileTreeNode({ node, onSelect, selectedPath }: { node: RepositoryFileNode, onSelect: (node: RepositoryFileNode) => void, selectedPath?: string }) {
  const [expanded, setExpanded] = useState(true)
  const isSelected = selectedPath === node.path

  return (
    <div className="text-sm">
      <div 
        className={`flex items-center justify-between p-1 rounded cursor-pointer transition-colors ${
          isSelected ? 'bg-[#37373d] text-white' : 'text-gray-300 hover:bg-[#333] hover:text-gray-100'
        }`}
        onClick={() => {
          if (node.type === 'directory') setExpanded(!expanded)
          onSelect(node)
        }}
      >
        <div className="flex items-center space-x-2 truncate">
          {node.type === 'directory' ? (
             expanded ? <ChevronDown className="w-4 h-4 shrink-0 text-gray-400" /> : <ChevronRight className="w-4 h-4 shrink-0 text-gray-400" />
          ) : (
            <span className="w-4 shrink-0" /> // Spacer for alignment
          )}
          
          <span className="truncate">{node.name}</span>
          
          {/* Indicators */}
          <div className="flex items-center space-x-1 shrink-0 ml-2">
            {node.isEntrypoint && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-green-500/20 text-green-400 border border-green-500/30 uppercase">Entry</span>
            )}
            {node.ownershipLabel && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-400 border border-purple-500/30">@{node.ownershipLabel}</span>
            )}
            
            {/* Blast Radius / Heat Indicators */}
            {node.referencedByCount !== undefined && node.referencedByCount > 2 && (
              <span className="w-1.5 h-1.5 rounded-full bg-red-500" title="Critical Infrastructure (High Blast Radius)" />
            )}
            {node.referencedByCount !== undefined && node.referencedByCount > 0 && node.referencedByCount <= 2 && (
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-500" title="Shared Dependency" />
            )}
            {node.referencedByCount === 0 && (
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 opacity-50" title="Isolated Module" />
            )}
            
            {node.mutationHeat === 'high' && (
              <span className="w-1.5 h-1.5 rounded-full bg-red-500/50" title="High Mutation Zone" />
            )}
            {node.mutationHeat === 'medium' && (
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-500/50" title="Medium Mutation Zone" />
            )}
          </div>
        </div>
      </div>
      
      {node.type === 'directory' && expanded && node.children && (
        <div className="pl-4 mt-1 border-l border-[#333] ml-2 space-y-1">
          {node.children.map((child, i) => (
            <FileTreeNode key={i} node={child} onSelect={onSelect} selectedPath={selectedPath} />
          ))}
        </div>
      )}
    </div>
  )
}

