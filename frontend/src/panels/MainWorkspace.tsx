import { useCallback, useEffect, useState } from "react"
import { AlertCircle, Check, Code2, Loader2, RotateCcw, Save } from "lucide-react"
import PromptWorkspace from "./PromptWorkspace"
import StatusBar from "../components/StatusBar"
import RepositoryExplorer from "./RepositoryExplorer"
import PreviewPanel from "./PreviewPanel"
import { ErrorBoundary } from "../components/ErrorBoundary"
import type { WorkspaceMode } from "../layouts/WorkspaceLayout"
import { useWorkspaceStore } from "../stores/workspace.store"
import { usePreviewStore } from "../stores/preview.store"
import { fetchFileContent, saveFileContent } from "../api/workspace.api"

interface MainWorkspaceProps {
  activeView: WorkspaceMode
  onViewChange: (view: WorkspaceMode) => void
}

export default function MainWorkspace({ activeView, onViewChange }: MainWorkspaceProps) {
  const [showInternalFiles, setShowInternalFiles] = useState(false)
  const editorDirty = useWorkspaceStore(s => s.editorDirty)

  useEffect(() => {
    if (!editorDirty) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ""
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [editorDirty])

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
              <RepositoryExplorer showInternalFiles={showInternalFiles} onViewChange={onViewChange} />
            </div>
          </ErrorBoundary>
        )
      case 'generate':
        return <PromptWorkspace />
      case 'edit':
        return <EditCodePanel />
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

function EditCodePanel() {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const activeRunId = useWorkspaceStore(s => s.activeRunId)
  const selectedEditorFile = useWorkspaceStore(s => s.selectedEditorFile)
  const editorWorkspaceId = useWorkspaceStore(s => s.editorWorkspaceId)
  const editorRunId = useWorkspaceStore(s => s.editorRunId)
  const editorContent = useWorkspaceStore(s => s.editorContent)
  const editorDirty = useWorkspaceStore(s => s.editorDirty)
  const editorSaving = useWorkspaceStore(s => s.editorSaving)
  const editorError = useWorkspaceStore(s => s.editorError)
  const setEditorContent = useWorkspaceStore(s => s.setEditorContent)
  const setEditorSaving = useWorkspaceStore(s => s.setEditorSaving)
  const setEditorError = useWorkspaceStore(s => s.setEditorError)
  const markEditorSaved = useWorkspaceStore(s => s.markEditorSaved)
  const clearEditorState = useWorkspaceStore(s => s.clearEditorState)
  const hardRefresh = usePreviewStore(s => s.hardRefresh)
  const [editorReloading, setEditorReloading] = useState(false)

  useEffect(() => {
    if (!selectedEditorFile) return
    const activeRunKey = activeRunId || null
    const editorRunKey = editorRunId || null
    const editorContextChanged = editorWorkspaceId !== activeWorkspaceId || editorRunKey !== activeRunKey
    if (!editorContextChanged) return

    if (!editorDirty || window.confirm("Discard unsaved editor changes for the previous project or run?")) {
      clearEditorState()
    }
  }, [
    activeRunId,
    activeWorkspaceId,
    clearEditorState,
    editorDirty,
    editorRunId,
    editorWorkspaceId,
    selectedEditorFile,
  ])

  const saveCurrentFile = useCallback(async () => {
    if (editorSaving) return
    if (!activeWorkspaceId) {
      setEditorError("No active workspace is available.")
      return
    }
    if (!selectedEditorFile) {
      setEditorError("Select a file from Explore before saving.")
      return
    }
    if (!selectedEditorFile.pathId) {
      setEditorError("Cannot save this file because its path identifier is missing.")
      return
    }
    if (editorWorkspaceId !== activeWorkspaceId) {
      setEditorError("This editor selection belongs to a different workspace. Reopen the file from Explore.")
      return
    }
    if ((editorRunId || null) !== (activeRunId || null)) {
      setEditorError("This editor selection belongs to a different run. Reopen the file from Explore.")
      return
    }
    if (!editorDirty) return

    setEditorSaving(true)
    setEditorError(null)
    try {
      const response = await saveFileContent(
        activeWorkspaceId,
        selectedEditorFile.pathId,
        editorContent,
        activeRunId || undefined,
      )
      if (response.error || response.ok === false) {
        throw new Error(response.error || "Backend rejected the file save.")
      }
      markEditorSaved(editorContent)
      hardRefresh()
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Failed to save file.")
      setEditorSaving(false)
    }
  }, [
    activeRunId,
    activeWorkspaceId,
    editorContent,
    editorDirty,
    editorSaving,
    editorRunId,
    editorWorkspaceId,
    hardRefresh,
    markEditorSaved,
    selectedEditorFile,
    setEditorError,
    setEditorSaving,
  ])

  const reloadCurrentFile = useCallback(async () => {
    if (editorReloading || editorSaving) return
    if (!activeWorkspaceId) {
      setEditorError("No active workspace is available.")
      return
    }
    if (!selectedEditorFile) {
      setEditorError("Select a file from Explore before reloading.")
      return
    }
    if (!selectedEditorFile.pathId) {
      setEditorError("Cannot reload this file because its path identifier is missing.")
      return
    }
    if (editorWorkspaceId !== activeWorkspaceId) {
      setEditorError("This editor selection belongs to a different workspace. Reopen the file from Explore.")
      return
    }
    if ((editorRunId || null) !== (activeRunId || null)) {
      setEditorError("This editor selection belongs to a different run. Reopen the file from Explore.")
      return
    }
    if (editorDirty && !window.confirm("Discard unsaved editor changes and reload from disk?")) {
      return
    }

    setEditorReloading(true)
    setEditorError(null)
    try {
      const response = await fetchFileContent(
        activeWorkspaceId,
        selectedEditorFile.pathId,
        activeRunId || undefined,
      )
      if (response.error) throw new Error(response.error)
      if (response.truncated) throw new Error("Cannot reload truncated file content into the editor.")
      markEditorSaved(typeof response.content === "string" ? response.content : "")
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : "Failed to reload file from disk.")
    } finally {
      setEditorReloading(false)
    }
  }, [
    activeRunId,
    activeWorkspaceId,
    editorDirty,
    editorReloading,
    editorRunId,
    editorSaving,
    editorWorkspaceId,
    markEditorSaved,
    selectedEditorFile,
    setEditorError,
  ])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault()
        void saveCurrentFile()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [saveCurrentFile])

  if (!selectedEditorFile) {
    return (
      <div className="flex h-full items-center justify-center bg-[#1e1e1e] p-8 text-center">
        <div className="max-w-md">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-panel">
            <Code2 className="h-5 w-5 text-blue-300" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-gray-100">Edit Code</h2>
          <p className="mt-2 text-sm text-gray-400">Select a file from Explore to edit.</p>
        </div>
      </div>
    )
  }

  const statusLabel = editorSaving ? "Saving..." : editorDirty ? "Unsaved" : "Saved"
  const hasEditorContextMismatch = editorWorkspaceId !== activeWorkspaceId || (editorRunId || null) !== (activeRunId || null)

  return (
    <div className="flex h-full flex-col bg-[#1e1e1e] text-gray-200">
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-[#333] bg-[#1e1e1e] px-6">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <Code2 className="h-5 w-5 shrink-0 text-blue-300" />
            <h2 className="truncate text-base font-semibold text-gray-100">{selectedEditorFile.name}</h2>
            {selectedEditorFile.language && (
              <span className="rounded border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] uppercase tracking-widest text-blue-300">
                {selectedEditorFile.language}
              </span>
            )}
          </div>
          <p className="mt-1 truncate text-xs text-gray-500">{selectedEditorFile.path}</p>
        </div>

        <div className="flex shrink-0 items-center gap-3 pl-4">
          <span className={`inline-flex h-7 items-center gap-1.5 rounded border px-2.5 text-xs ${
            editorDirty
              ? "border-yellow-400/30 bg-yellow-500/10 text-yellow-300"
              : "border-green-400/30 bg-green-500/10 text-green-300"
          }`}>
            {!editorDirty && !editorSaving && <Check className="h-3.5 w-3.5" />}
            {editorSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={() => void reloadCurrentFile()}
            disabled={editorSaving || editorReloading || hasEditorContextMismatch}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm font-medium text-gray-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {editorReloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
            {editorReloading ? "Reloading..." : "Reload"}
          </button>
          <button
            type="button"
            onClick={() => void saveCurrentFile()}
            disabled={!editorDirty || editorSaving || editorReloading || hasEditorContextMismatch}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-blue-400/30 bg-blue-500/10 px-3 text-sm font-medium text-blue-100 transition hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-45"
          >
            {editorSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {editorSaving ? "Saving..." : editorDirty ? "Save" : "Saved"}
          </button>
        </div>
      </div>

      {editorError && (
        <div className="flex shrink-0 items-start gap-2 border-b border-red-500/20 bg-red-500/10 px-6 py-3 text-sm text-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{editorError}</span>
        </div>
      )}

      <textarea
        value={editorContent}
        onChange={(event) => setEditorContent(event.target.value)}
        spellCheck={false}
        className="min-h-0 flex-1 resize-none border-0 bg-[#1e1e1e] p-5 font-mono text-sm leading-6 text-gray-200 outline-none placeholder:text-gray-600 focus:ring-0"
        aria-label={`Editing ${selectedEditorFile.path}`}
      />
    </div>
  )
}
