import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"
import type { RepositoryFileNode } from "../stores/workspace.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { usePreviewStore } from "../stores/preview.store"
import { Box, ChevronDown, ChevronRight, Code, FileCode, FilePlus, FileText, Folder, FolderOpen, FolderPlus, Hash, MoveRight, Pencil, Trash2 } from "lucide-react"
import { createWorkspaceEntry, deleteWorkspaceEntry, fetchFileContent, moveWorkspaceEntry } from "../api/workspace.api"
import FileInspector from "./FileInspector"
import type { WorkspaceMode } from "../stores/workspace.store"

interface RepositoryExplorerProps {
  showInternalFiles?: boolean
  onViewChange: (view: WorkspaceMode) => void
  sidebar?: boolean
}

export default function RepositoryExplorer({ showInternalFiles: showInternalFilesProp, onViewChange, sidebar = false }: RepositoryExplorerProps) {
  const [localShowInternalFiles, setLocalShowInternalFiles] = useState(false)
  const showInternalFiles = showInternalFilesProp !== undefined ? showInternalFilesProp : localShowInternalFiles
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const repositorySnapshot = useWorkspaceStore(s => s.repositorySnapshot)
  const activeRunId = useWorkspaceStore(s => s.activeRunId)
  const runHistory = useWorkspaceStore(s => s.runHistory)
  const workspaceHydrationStatus = useWorkspaceStore(s => s.workspaceHydrationStatus)
  const workspaceHydrationError = useWorkspaceStore(s => s.workspaceHydrationError)
  const loadRunData = useWorkspaceStore(s => s.loadRunData)
  const loadWorkspaceData = useWorkspaceStore(s => s.loadWorkspaceData)
  const selectedEditorFile = useWorkspaceStore(s => s.selectedEditorFile)
  const editorDirty = useWorkspaceStore(s => s.editorDirty)
  const openFileInEditor = useWorkspaceStore(s => s.openFileInEditor)
  const clearEditorState = useWorkspaceStore(s => s.clearEditorState)
  const updateEditorFileMetadata = useWorkspaceStore(s => s.updateEditorFileMetadata)
  const selectedExplorerNode = useWorkspaceStore(s => s.selectedExplorerNode)
  const explorerSelectionWorkspaceId = useWorkspaceStore(s => s.explorerSelectionWorkspaceId)
  const explorerSelectionRunId = useWorkspaceStore(s => s.explorerSelectionRunId)
  const explorerCollapsedFolderPaths = useWorkspaceStore(s => s.explorerCollapsedFolderPaths)
  const explorerCollapseWorkspaceId = useWorkspaceStore(s => s.explorerCollapseWorkspaceId)
  const explorerCollapseRunId = useWorkspaceStore(s => s.explorerCollapseRunId)
  const selectExplorerNode = useWorkspaceStore(s => s.selectExplorerNode)
  const clearExplorerSelection = useWorkspaceStore(s => s.clearExplorerSelection)
  const toggleExplorerFolder = useWorkspaceStore(s => s.toggleExplorerFolder)
  const generationStatus = usePreviewStore(s => s.generationStatus)
  const generationFailure = usePreviewStore(s => s.generationFailure)
  const [operationError, setOperationError] = useState<string | null>(null)
  const [operationBusy, setOperationBusy] = useState(false)

  const repositoryTree = prioritizeAppFiles(filterInternalFiles(Array.isArray(repositorySnapshot?.tree) ? repositorySnapshot.tree : [], showInternalFiles))
  const mutationRunId = activeRunId || repositorySnapshot?.runId || null
  const latestGenerationFailed = isFailureStatus(generationStatus?.status) || Boolean(generationFailure)
  const failureMessage = generationFailure?.message || generationStatus?.message || workspaceHydrationError
  const hasSuccessfulRun = runHistory.some(run => isSuccessfulRunStatus(run.status))
  const hasActiveSource = Boolean(activeRunId || hasSuccessfulRun)
  const selectionMatchesTree =
    explorerSelectionWorkspaceId === activeWorkspaceId &&
    (explorerSelectionRunId || null) === (mutationRunId || null)
  const selectedFile = selectionMatchesTree && selectedExplorerNode
    ? findNodeInTree(repositoryTree, selectedExplorerNode)
    : null
  const collapseMatchesTree =
    explorerCollapseWorkspaceId === activeWorkspaceId &&
    (explorerCollapseRunId || null) === (mutationRunId || null)
  const collapsedFolderPaths = collapseMatchesTree ? explorerCollapsedFolderPaths : []

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
    const node = findNodeByPath(repositoryTree, filePath)
    if (node && activeWorkspaceId) selectExplorerNode(node, activeWorkspaceId, mutationRunId)
  }

  const refreshRepository = useCallback(async () => {
    if (!activeWorkspaceId) return
    if (mutationRunId) {
      await loadRunData(activeWorkspaceId, mutationRunId)
    } else {
      await loadWorkspaceData(activeWorkspaceId)
    }
  }, [activeWorkspaceId, loadRunData, loadWorkspaceData, mutationRunId])

  const runMutation = useCallback(async (operation: () => Promise<RepositoryFileNode | null>) => {
    if (!activeWorkspaceId) {
      setOperationError("No active workspace is available.")
      return
    }
    if (!mutationRunId) {
      setOperationError("No active run is available for file operations.")
      return
    }

    setOperationBusy(true)
    setOperationError(null)
    try {
      const nextSelectedFile = await operation()
      await refreshRepository()
      if (nextSelectedFile) selectExplorerNode(nextSelectedFile, activeWorkspaceId, mutationRunId)
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : "File operation failed.")
    } finally {
      setOperationBusy(false)
    }
  }, [activeWorkspaceId, mutationRunId, refreshRepository])

  const handleCreateEntry = useCallback((entryType: "file" | "directory", parent?: RepositoryFileNode) => {
    const parentPrefix = parent?.type === "directory" && parent.path ? `${parent.path}/` : ""
    const defaultPath = `${parentPrefix}${entryType === "file" ? "new-file.ts" : "new-folder"}`
    const path = window.prompt(entryType === "file" ? "New file path" : "New folder path", defaultPath)
    if (!path) return

    void runMutation(async () => {
      const response = await createWorkspaceEntry(activeWorkspaceId || "", {
        path,
        type: entryType,
        content: entryType === "file" ? "" : undefined,
      }, mutationRunId)
      return {
        name: response.name || path.split(/[\\/]/).pop() || path,
        path: response.path,
        pathId: response.pathId,
        type: response.type,
      }
    })
  }, [activeWorkspaceId, mutationRunId, runMutation])

  const handleRenameEntry = useCallback((node: RepositoryFileNode) => {
    if (!node.pathId) {
      setOperationError("This entry cannot be renamed because its path identifier is missing.")
      return
    }
    const parentPath = node.path.includes("/") ? `${node.path.slice(0, node.path.lastIndexOf("/") + 1)}` : ""
    const nextName = window.prompt("Rename to", node.name)
    if (!nextName || nextName === node.name) return
    const nextPath = `${parentPath}${nextName.replace(/^[/\\]+/, "")}`

    void runMutation(async () => {
      const response = await moveWorkspaceEntry(activeWorkspaceId || "", node.pathId || "", nextPath, mutationRunId)
      const updatedNode: RepositoryFileNode = {
        name: response.name || nextName,
        path: response.path,
        pathId: response.pathId,
        type: response.type,
        children: node.children,
      }
      if (selectedEditorFile?.pathId === node.pathId) {
        updateEditorFileMetadata({
          name: updatedNode.name,
          path: updatedNode.path,
          pathId: updatedNode.pathId || "",
          language: response.language,
        }, activeWorkspaceId || "", mutationRunId)
      }
      return selectedFile?.pathId === node.pathId ? updatedNode : null
    })
  }, [activeWorkspaceId, mutationRunId, runMutation, selectedEditorFile?.pathId, selectedFile?.pathId, updateEditorFileMetadata])

  const handleMoveEntry = useCallback((node: RepositoryFileNode) => {
    if (!node.pathId) {
      setOperationError("This entry cannot be moved because its path identifier is missing.")
      return
    }
    const nextPath = window.prompt("Move to path", node.path)
    if (!nextPath || nextPath === node.path) return

    void runMutation(async () => {
      const response = await moveWorkspaceEntry(activeWorkspaceId || "", node.pathId || "", nextPath, mutationRunId)
      const updatedNode: RepositoryFileNode = {
        name: response.name || nextPath.split(/[\\/]/).pop() || node.name,
        path: response.path,
        pathId: response.pathId,
        type: response.type,
        children: node.children,
      }
      if (selectedEditorFile?.pathId === node.pathId) {
        updateEditorFileMetadata({
          name: updatedNode.name,
          path: updatedNode.path,
          pathId: updatedNode.pathId || "",
          language: response.language,
        }, activeWorkspaceId || "", mutationRunId)
      }
      return selectedFile?.pathId === node.pathId ? updatedNode : null
    })
  }, [activeWorkspaceId, mutationRunId, runMutation, selectedEditorFile?.pathId, selectedFile?.pathId, updateEditorFileMetadata])

  const handleDeleteEntry = useCallback((node: RepositoryFileNode) => {
    if (!node.pathId) {
      setOperationError("This entry cannot be deleted because its path identifier is missing.")
      return
    }
    const message = node.type === "directory"
      ? `Delete folder "${node.path}" and all of its contents?`
      : `Delete file "${node.path}"?`
    if (!window.confirm(message)) return

    void runMutation(async () => {
      await deleteWorkspaceEntry(activeWorkspaceId || "", node.pathId || "", mutationRunId)
      if (selectedFile?.pathId === node.pathId) clearExplorerSelection()
      if (selectedEditorFile?.pathId === node.pathId) clearEditorState()
      return null
    })
  }, [activeWorkspaceId, clearEditorState, clearExplorerSelection, mutationRunId, runMutation, selectedEditorFile?.pathId, selectedFile?.pathId])

  const handleSelectNode = useCallback((node: RepositoryFileNode) => {
    if (!activeWorkspaceId) return
    selectExplorerNode(node, activeWorkspaceId, mutationRunId)
  }, [activeWorkspaceId, mutationRunId, selectExplorerNode])

  const handleToggleFolder = useCallback((path: string) => {
    if (!activeWorkspaceId) return
    toggleExplorerFolder(path, activeWorkspaceId, mutationRunId)
  }, [activeWorkspaceId, mutationRunId, toggleExplorerFolder])

  const handleOpenFile = useCallback(async (node: RepositoryFileNode) => {
    if (!activeWorkspaceId || node.type !== "file") return
    if (!node.pathId) {
      setOperationError("This file cannot be opened because its path identifier is missing.")
      return
    }
    if (editorDirty && selectedEditorFile?.pathId !== node.pathId && !window.confirm("Discard unsaved editor changes and open this file?")) {
      return
    }

    setOperationError(null)
    try {
      const response = await fetchFileContent(activeWorkspaceId, node.pathId, mutationRunId || undefined)
      if (response.error) throw new Error(response.error)
      if (response.truncated) throw new Error("Cannot open truncated file content in the editor.")

      openFileInEditor({
        name: node.name,
        path: node.path,
        pathId: node.pathId,
        language: response.language || languageFromPath(node.path),
      }, typeof response.content === "string" ? response.content : "", activeWorkspaceId, mutationRunId)
      onViewChange("edit")
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : "Failed to open file.")
    }
  }, [
    activeWorkspaceId,
    editorDirty,
    mutationRunId,
    onViewChange,
    openFileInEditor,
    selectedEditorFile?.pathId,
  ])

  useEffect(() => {
    if (!selectedExplorerNode) return
    if (!selectionMatchesTree) return
    const stillExists = selectedExplorerNode.pathId
      ? treeContainsPathId(repositoryTree, selectedExplorerNode.pathId)
      : Boolean(findNodeByPath(repositoryTree, selectedExplorerNode.path))
    if (!stillExists) clearExplorerSelection()
  }, [clearExplorerSelection, repositoryTree, selectedExplorerNode, selectionMatchesTree])

  if (!repositorySnapshot || repositoryTree.length === 0) {
    if (sidebar) {
      return (
        <div className="flex h-full flex-col bg-[#181818] overflow-hidden text-gray-500 text-xs p-4 justify-center items-center">
          <FileCode className="mx-auto mb-3 h-8 w-8 text-gray-600 opacity-40" />
          <p className="text-center font-semibold text-gray-300">No project files</p>
          <p className="text-center mt-1 text-[11px] text-gray-500">Generate or promote a run first.</p>
        </div>
      )
    }
    const isLoading = workspaceHydrationStatus === 'loading'
    const title = isLoading
      ? "Loading files..."
      : latestGenerationFailed || !hasActiveSource
        ? "No active successful run yet."
        : "No files to show."

    const description = isLoading
      ? "Reading the active workspace source tree."
      : latestGenerationFailed
        ? "Generation failed before a runnable project was promoted. Explore will show files after a successful generation."
        : !hasActiveSource
          ? "Generate a smaller MVP successfully to browse source files here."
          : "The active run did not return visible source files."

    return (
      <RepositoryEmptyState
        title={title}
        description={description}
        detail={!isLoading && failureMessage ? failureMessage : null}
      />
    )
  }

  if (sidebar) {
    return (
      <div className="flex flex-col h-full bg-[#181818] overflow-hidden text-gray-300 font-mono">
        {/* Header */}
        <div className="flex h-11 shrink-0 items-center justify-between border-b border-[#2d2d2d] px-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">
            Explorer
          </div>
          <div className="flex items-center space-x-1.5">
            <button
              type="button"
              onClick={() => handleCreateEntry("file")}
              disabled={operationBusy}
              title="New File"
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-[#2d2d2d] hover:border-blue-400/40 text-gray-400 hover:text-blue-300 transition disabled:opacity-40"
            >
              <FilePlus className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => handleCreateEntry("directory")}
              disabled={operationBusy}
              title="New Folder"
              className="inline-flex h-6 w-6 items-center justify-center rounded border border-[#2d2d2d] hover:border-blue-400/40 text-gray-400 hover:text-blue-300 transition disabled:opacity-40"
            >
              <FolderPlus className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Support Files Checkbox */}
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#2d2d2d] bg-[#151515] text-[10px] text-gray-400">
          <span>Support Files</span>
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              className="rounded border-[#2d2d2d] bg-[#1e1e1e] text-blue-500 focus:ring-0 w-3 h-3"
              checked={showInternalFiles}
              onChange={(e) => setLocalShowInternalFiles(e.target.checked)}
            />
            Show
          </label>
        </div>

        {/* Tree Container */}
        <div className="min-h-0 flex-1 overflow-auto py-2">
          {operationError && (
            <div className="mx-3 mb-2 rounded border border-red-500/30 bg-red-500/10 px-2 py-1 text-[11px] text-red-300">
              {operationError}
            </div>
          )}
          <div className="space-y-0.5 px-1.5">
            {repositoryTree.map((node, i) => (
              <FileTreeNode
                key={i}
                node={node}
                onCreate={handleCreateEntry}
                onDelete={handleDeleteEntry}
                onMove={handleMoveEntry}
                onRename={handleRenameEntry}
                onOpenFile={handleOpenFile}
                onSelect={(n) => {
                  if (n.type === "file") {
                    handleOpenFile(n);
                  } else {
                    handleSelectNode(n);
                  }
                }}
                onToggleFolder={handleToggleFolder}
                collapsedFolderPaths={collapsedFolderPaths}
                operationBusy={operationBusy}
                selectedPath={selectedFile?.path}
                activePathId={selectedEditorFile?.pathId}
              />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono overflow-hidden">
      <div className="border-b border-[#333] px-6 py-4 flex items-center justify-between shrink-0 bg-[#1e1e1e]">
        <div className="flex items-center space-x-3">
          <Folder className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg text-gray-100 font-medium">Files</h2>
        </div>
        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={() => handleCreateEntry("file")}
            disabled={operationBusy}
            title="New File"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-[#3c3c3c] text-gray-300 transition hover:border-blue-400/40 hover:text-blue-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <FilePlus className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => handleCreateEntry("directory")}
            disabled={operationBusy}
            title="New Folder"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-[#3c3c3c] text-gray-300 transition hover:border-blue-400/40 hover:text-blue-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <FolderPlus className="h-4 w-4" />
          </button>
          {activeRunId && (
            <div className="flex items-center space-x-2 text-xs">
              <span className="text-gray-500">Run:</span>
              <span className="text-blue-400 font-bold">{activeRunId}</span>
            </div>
          )}
          <div className="text-xs text-gray-500 border-l border-[#333] pl-4">
            {repositorySnapshot.totalFiles ?? repositoryTree.length} files • {repositorySnapshot.ecosystem || 'unknown'}
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left: File Tree */}
        <div className="w-80 shrink-0 border-r border-[#333] p-4 overflow-y-auto bg-[#252526]">
          <div className="text-xs uppercase tracking-widest text-gray-500 font-bold mb-4">
            {showInternalFiles ? 'Project Files' : 'App Files'}
          </div>
          {operationError && (
            <div className="mb-3 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
              {operationError}
            </div>
          )}
          <div className="space-y-1">
            {repositoryTree.map((node, i) => (
              <FileTreeNode
                key={i}
                node={node}
                onCreate={handleCreateEntry}
                onDelete={handleDeleteEntry}
                onMove={handleMoveEntry}
                onRename={handleRenameEntry}
                onOpenFile={handleOpenFile}
                onSelect={handleSelectNode}
                onToggleFolder={handleToggleFolder}
                collapsedFolderPaths={collapsedFolderPaths}
                operationBusy={operationBusy}
                selectedPath={selectedFile?.path}
                activePathId={selectedEditorFile?.pathId}
              />
            ))}
          </div>
        </div>

        {/* Right: Metadata Inspector / File Inspector */}
        <div className="flex-1 overflow-hidden bg-[#1e1e1e]">
          {!selectedFile ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <FileCode className="w-12 h-12 mb-4 opacity-20" />
              <p>Select a file to inspect content and symbols.</p>
            </div>
          ) : selectedFile.type === 'directory' ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <Folder className="w-12 h-12 mb-4 opacity-20 text-blue-400" />
              <p>Directory selected: {selectedFile.name}</p>
            </div>
          ) : (
            <FileInspector file={selectedFile} onSymbolClick={handleSymbolClick} onViewChange={onViewChange} />
          )}
        </div>
      </div>
    </div>
  )
}

function isFailureStatus(status: unknown): boolean {
  const normalized = String(status || '').toLowerCase()
  return normalized === 'failed' || normalized === 'failure' || normalized === 'runtime_failed'
}

function isSuccessfulRunStatus(status: unknown): boolean {
  const normalized = String(status || '').toLowerCase()
  return normalized === 'success' || normalized === 'succeeded'
}

function RepositoryEmptyState({
  title,
  description,
  detail,
}: {
  title: string
  description: string
  detail?: string | null
}) {
  return (
    <div className="flex h-full flex-col bg-[#1e1e1e] text-gray-300 font-mono overflow-hidden">
      <div className="border-b border-[#333] px-6 py-4 flex items-center justify-between shrink-0 bg-[#1e1e1e]">
        <div className="flex items-center space-x-3">
          <Folder className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg text-gray-100 font-medium">Files</h2>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center p-8 text-center text-gray-500">
        <div className="max-w-md">
          <FileCode className="mx-auto mb-4 h-10 w-10 text-gray-600" />
          <h3 className="text-base font-semibold text-gray-200">{title}</h3>
          <p className="mt-2 text-sm leading-6">{description}</p>
          {detail && (
            <p className="mt-3 rounded-md border border-[#333] bg-[#252526] px-3 py-2 text-xs text-gray-400">
              {detail}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

function treeContainsPathId(nodes: RepositoryFileNode[], pathId: string): boolean {
  for (const node of nodes) {
    if (node.pathId === pathId) return true
    if (Array.isArray(node.children) && treeContainsPathId(node.children, pathId)) return true
  }
  return false
}

function findNodeInTree(nodes: RepositoryFileNode[], selected: { path: string; pathId?: string }): RepositoryFileNode | null {
  for (const node of nodes) {
    if (selected.pathId && node.pathId === selected.pathId) return node
    if (!selected.pathId && node.path === selected.path) return node
    if (Array.isArray(node.children)) {
      const child = findNodeInTree(node.children, selected)
      if (child) return child
    }
  }
  return null
}

function filterInternalFiles(nodes: RepositoryFileNode[], showInternalFiles: boolean): RepositoryFileNode[] {
  if (showInternalFiles) return nodes

  return nodes
    .filter((node) => {
      const path = node.path || node.name || ''
      return !path.includes('.orchestration') && !path.startsWith('workspaces/') && !path.includes('/.orchestration/')
    })
    .map((node) => ({
      ...node,
      children: Array.isArray(node.children) ? filterInternalFiles(node.children, showInternalFiles) : undefined,
    }))
}

function prioritizeAppFiles(nodes: RepositoryFileNode[]): RepositoryFileNode[] {
  const priority = (node: RepositoryFileNode) => {
    const path = node.path || node.name || ''
    if (path === 'src' || path.startsWith('src/')) return 0
    if (path === 'public' || path.startsWith('public/')) return 1
    if (path === 'package.json') return 2
    if (path.includes('vite.config')) return 3
    if (path.includes('tsconfig')) return 4
    return 10
  }

  return [...nodes]
    .sort((a, b) => priority(a) - priority(b) || (a.name || '').localeCompare(b.name || ''))
    .map((node) => ({
      ...node,
      children: Array.isArray(node.children) ? prioritizeAppFiles(node.children) : undefined,
    }))
}

function FileTreeNode({
  node,
  onCreate,
  onDelete,
  onMove,
  onOpenFile,
  onRename,
  onSelect,
  onToggleFolder,
  collapsedFolderPaths,
  operationBusy,
  activePathId,
  selectedPath,
}: {
  node: RepositoryFileNode
  onCreate: (entryType: "file" | "directory", parent?: RepositoryFileNode) => void
  onDelete: (node: RepositoryFileNode) => void
  onMove: (node: RepositoryFileNode) => void
  onOpenFile: (node: RepositoryFileNode) => void
  onRename: (node: RepositoryFileNode) => void
  onSelect: (node: RepositoryFileNode) => void
  onToggleFolder: (path: string) => void
  collapsedFolderPaths: string[]
  operationBusy: boolean
  activePathId?: string
  selectedPath?: string
}) {
  const expanded = !collapsedFolderPaths.includes(node.path)
  const isSelected = selectedPath === node.path
  const isActiveFile = node.type === "file" && Boolean(activePathId && node.pathId === activePathId)

  return (
    <div className="text-sm">
      <div 
        role="button"
        tabIndex={0}
        aria-label={`${node.type === "directory" ? "Select folder" : "Select file"} ${node.path}`}
        className={`group flex items-center justify-between gap-2 border-l-2 p-1 rounded cursor-pointer transition-colors ${
          isSelected
            ? 'border-blue-400 bg-[#37373d] text-white'
            : isActiveFile
              ? 'border-green-400/70 bg-green-500/10 text-green-100'
              : 'border-transparent text-gray-300 hover:bg-[#333] hover:text-gray-100'
        }`}
        onClick={() => {
          if (node.type === 'directory') onToggleFolder(node.path)
          onSelect(node)
        }}
        onDoubleClick={() => {
          if (node.type === "file") onOpenFile(node)
        }}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return
          event.preventDefault()
          if (node.type === "directory") onToggleFolder(node.path)
          onSelect(node)
        }}
      >
        <div className="flex items-center space-x-2 min-w-0">
          {node.type === 'directory' ? (
            <>
              {expanded ? <ChevronDown className="w-4 h-4 shrink-0 text-gray-400" /> : <ChevronRight className="w-4 h-4 shrink-0 text-gray-400" />}
              {expanded ? <FolderOpen className="w-4 h-4 shrink-0 text-yellow-300/80" /> : <Folder className="w-4 h-4 shrink-0 text-yellow-300/80" />}
            </>
          ) : (
            <>
              <span className="w-4 shrink-0" />
              <FileTypeIcon path={node.path} />
            </>
          )}
          
          <span className="truncate">{node.name}</span>
          {isActiveFile && (
            <span className="rounded border border-green-400/30 bg-green-500/10 px-1.5 py-0.5 text-[10px] uppercase text-green-300">
              Open
            </span>
          )}
          
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
        <div className="flex shrink-0 items-center gap-1 opacity-0 transition group-hover:opacity-100 group-focus-within:opacity-100">
          {node.type === "directory" && (
            <>
              <TreeActionButton disabled={operationBusy} title="New File" onClick={() => onCreate("file", node)}>
                <FilePlus className="h-3.5 w-3.5" />
              </TreeActionButton>
              <TreeActionButton disabled={operationBusy} title="New Folder" onClick={() => onCreate("directory", node)}>
                <FolderPlus className="h-3.5 w-3.5" />
              </TreeActionButton>
            </>
          )}
          <TreeActionButton disabled={operationBusy} title="Rename" onClick={() => onRename(node)}>
            <Pencil className="h-3.5 w-3.5" />
          </TreeActionButton>
          <TreeActionButton disabled={operationBusy} title="Move" onClick={() => onMove(node)}>
            <MoveRight className="h-3.5 w-3.5" />
          </TreeActionButton>
          <TreeActionButton disabled={operationBusy} title="Delete" onClick={() => onDelete(node)}>
            <Trash2 className="h-3.5 w-3.5" />
          </TreeActionButton>
        </div>
      </div>
      
      {node.type === 'directory' && expanded && Array.isArray(node.children) && (
        <div className="pl-4 mt-1 border-l border-[#333] ml-2 space-y-1">
          {node.children.map((child, i) => (
            <FileTreeNode
              key={i}
              node={child}
              onCreate={onCreate}
              onDelete={onDelete}
              onMove={onMove}
              onRename={onRename}
              onOpenFile={onOpenFile}
              onSelect={onSelect}
              onToggleFolder={onToggleFolder}
              collapsedFolderPaths={collapsedFolderPaths}
              operationBusy={operationBusy}
              activePathId={activePathId}
              selectedPath={selectedPath}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function FileTypeIcon({ path }: { path: string }) {
  const extension = path.split(".").pop()?.toLowerCase() || ""

  if (["ts", "tsx", "js", "jsx", "py", "php"].includes(extension)) {
    return <Code className="w-4 h-4 shrink-0 text-blue-300/80" />
  }
  if (["json", "yml", "yaml", "env"].includes(extension)) {
    return <Hash className="w-4 h-4 shrink-0 text-yellow-300/80" />
  }
  if (["css", "html"].includes(extension)) {
    return <Box className="w-4 h-4 shrink-0 text-purple-300/80" />
  }

  return <FileText className="w-4 h-4 shrink-0 text-gray-500" />
}

function languageFromPath(path: string): string {
  const extension = path.split(".").pop()?.toLowerCase()
  if (!extension) return "text"

  const map: Record<string, string> = {
    css: "css",
    env: "env",
    html: "html",
    js: "javascript",
    jsx: "jsx",
    json: "json",
    md: "markdown",
    php: "php",
    py: "python",
    ts: "typescript",
    tsx: "tsx",
    txt: "text",
    yaml: "yaml",
    yml: "yaml",
  }

  return map[extension] || extension
}

function TreeActionButton({
  children,
  disabled,
  onClick,
  title,
}: {
  children: ReactNode
  disabled: boolean
  onClick: () => void
  title: string
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={title}
      onClick={(event) => {
        event.stopPropagation()
        onClick()
      }}
      className="inline-flex h-6 w-6 items-center justify-center rounded text-gray-400 transition hover:bg-[#404047] hover:text-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  )
}
