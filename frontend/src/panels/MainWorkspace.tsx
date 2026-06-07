import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Panel, Group, Separator } from "react-resizable-panels"
import Editor from "@monaco-editor/react"
import {
  AlertCircle,
  Check,
  Code2,
  Loader2,
  RotateCcw,
  Save,
} from "lucide-react"
import PromptWorkspace from "./PromptWorkspace"
import StatusBar from "../components/StatusBar"
import RepositoryExplorer from "./RepositoryExplorer"
import PreviewPanel from "./PreviewPanel"
import FileInspector from "./FileInspector"
import WorkspaceOverview from "./WorkspaceOverview"
import RunHistory from "./RunHistory"
import TerminalPanel from "./TerminalPanel"
import ArtifactExplorer from "./ArtifactExplorer"
import SkillsPanel from "./SkillsPanel"
import DebugObservatory from "./DebugObservatory"
import SettingsPanel from "./SettingsPanel"
import { ErrorBoundary } from "../components/ErrorBoundary"
import { useWorkspaceStore } from "../stores/workspace.store"
import type { WorkspaceMode } from "../stores/workspace.store"
import { usePreviewStore } from "../stores/preview.store"
import { fetchFileContent, saveFileContent } from "../api/workspace.api"
import { shouldClearMissingEditorFile } from "../stateConsistency"

interface MainWorkspaceProps {
  activeView: WorkspaceMode
  onViewChange: (view: WorkspaceMode) => void
}

export default function MainWorkspace({ activeView, onViewChange }: MainWorkspaceProps) {
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
         return <EditCodePanel onViewChange={onViewChange} />
      case 'generate':
        return <PromptWorkspace />
      case 'edit':
         return <EditCodePanel onViewChange={onViewChange} />
      case 'overview':
        return (
          <ErrorBoundary fallbackName="Workspace Overview">
            <WorkspaceOverview />
          </ErrorBoundary>
        )
      case 'history':
        return (
          <ErrorBoundary fallbackName="Run History">
            <RunHistory />
          </ErrorBoundary>
        )
      case 'terminal':
        return (
          <ErrorBoundary fallbackName="Terminal Panel">
            <TerminalPanel />
          </ErrorBoundary>
        )
      case 'artifacts':
        return (
          <ErrorBoundary fallbackName="Artifact Explorer">
            <ArtifactExplorer />
          </ErrorBoundary>
        )
      case 'skills':
        return (
          <ErrorBoundary fallbackName="Skills Panel">
            <SkillsPanel />
          </ErrorBoundary>
        )
      case 'debug':
        return (
          <ErrorBoundary fallbackName="Debug Inspector">
            <DebugObservatory />
          </ErrorBoundary>
        )
      case 'settings':
        return (
          <ErrorBoundary fallbackName="Settings Panel">
            <SettingsPanel />
          </ErrorBoundary>
        )
      default:
        return <PromptWorkspace />
    }
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-[#1e1e1e]">
      <div className="flex min-h-0 flex-1 overflow-hidden bg-[#1e1e1e]">
        {renderView()}
      </div>
      <StatusBar />
    </div>
  )
}

function EditCodePanel({ onViewChange }: { onViewChange: (view: WorkspaceMode) => void }) {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const activeRunId = useWorkspaceStore(s => s.activeRunId)

  const repositorySnapshot = useWorkspaceStore(s => s.repositorySnapshot)
  const workspaceHydrationStatus = useWorkspaceStore(s => s.workspaceHydrationStatus)

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

  const openFileInEditor = useWorkspaceStore(s => s.openFileInEditor)

  const hardRefresh = usePreviewStore(s => s.hardRefresh)
  const [editorReloading, setEditorReloading] = useState(false)

  const restoredFileKeyRef = useRef<string | null>(null)

  const editorFiles = useMemo(() => collectEditableFiles(repositorySnapshot), [repositorySnapshot])
  const lineCount = useMemo(() => Math.max(1, editorContent.split("\n").length), [editorContent])
  const selectedEditorFileExists = useMemo(() => {
    if (!selectedEditorFile?.pathId) return false
    if (!repositorySnapshot) return true
    return editorFiles.some(file => file.pathId === selectedEditorFile.pathId)
  }, [editorFiles, repositorySnapshot, selectedEditorFile?.pathId])



  useEffect(() => {
    if (!selectedEditorFile) return
    if (workspaceHydrationStatus !== "ready") return
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
    workspaceHydrationStatus,
  ])

  useEffect(() => {
    if (!selectedEditorFile || !repositorySnapshot || selectedEditorFileExists) return

    const message = `The selected file "${selectedEditorFile.path}" does not exist in the current repository tree.`
    if (shouldClearMissingEditorFile({
      hasSelectedFile: Boolean(selectedEditorFile),
      hasRepositorySnapshot: Boolean(repositorySnapshot),
      selectedFileExists: selectedEditorFileExists,
      editorDirty,
    })) {
      clearEditorState()
    }
    setEditorError(message)
  }, [
    clearEditorState,
    editorDirty,
    repositorySnapshot,
    selectedEditorFile,
    selectedEditorFileExists,
    setEditorError,
  ])

  useEffect(() => {
    if (!activeWorkspaceId || !selectedEditorFile || !repositorySnapshot) return
    if (workspaceHydrationStatus !== "ready") return
    if (!selectedEditorFileExists) return
    if (editorDirty || editorContent !== "") return
    if (editorWorkspaceId !== activeWorkspaceId) return
    if ((editorRunId || null) !== (activeRunId || null)) return

    const restoreKey = `${activeWorkspaceId}:${activeRunId || ""}:${selectedEditorFile.pathId}`
    if (restoredFileKeyRef.current === restoreKey) return
    restoredFileKeyRef.current = restoreKey

    fetchFileContent(activeWorkspaceId, selectedEditorFile.pathId, activeRunId || undefined)
      .then((response) => {
        if (response.error) throw new Error(response.error)
        if (response.truncated) throw new Error("Cannot restore truncated file content into the editor.")
        markEditorSaved(typeof response.content === "string" ? response.content : "")
      })
      .catch((error) => {
        clearEditorState()
        setEditorError(error instanceof Error ? error.message : "Failed to restore selected file.")
      })
  }, [
    activeRunId,
    activeWorkspaceId,
    clearEditorState,
    editorContent,
    editorDirty,
    editorRunId,
    editorWorkspaceId,
    markEditorSaved,
    repositorySnapshot,
    selectedEditorFile,
    selectedEditorFileExists,
    setEditorError,
    workspaceHydrationStatus,
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
    if (!selectedEditorFileExists) {
      setEditorError("This file no longer exists in the current repository tree. Unsaved content was kept as a local draft.")
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
    selectedEditorFileExists,
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
    if (!selectedEditorFileExists) {
      setEditorError("This file no longer exists in the current repository tree.")
      if (!editorDirty) clearEditorState()
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
      const message = error instanceof Error ? error.message : "Failed to reload file from disk."
      if (!editorDirty) clearEditorState()
      setEditorError(message)
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
    clearEditorState,
    markEditorSaved,
    selectedEditorFile,
    selectedEditorFileExists,
    setEditorError,
  ])

  const openFileFromTree = useCallback(async (file: EditorFileEntry) => {
    if (!activeWorkspaceId) {
      setEditorError("No active workspace is available.")
      return
    }

    if (selectedEditorFile?.pathId === file.pathId) return

    if (editorDirty && !window.confirm("Discard unsaved editor changes and open another file?")) {
      return
    }

    setEditorError(null)

    try {
      const response = await fetchFileContent(
        activeWorkspaceId,
        file.pathId,
        activeRunId || undefined,
      )

      if (response.error) throw new Error(response.error)
      if (response.truncated) throw new Error("Cannot open truncated file content in the editor.")

      openFileInEditor(
        {
          name: file.name,
          path: file.path,
          pathId: file.pathId,
          language: file.language,
        },
        typeof response.content === "string" ? response.content : "",
        activeWorkspaceId,
        activeRunId || null,
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to open file."
      if (!editorDirty) {
        clearEditorState()
      }
      setEditorError(editorDirty ? `${message} Unsaved editor content was kept as a local draft.` : message)
    }
  }, [
    activeRunId,
    activeWorkspaceId,
    clearEditorState,
    editorDirty,
    openFileInEditor,
    selectedEditorFile?.pathId,
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

  const handleSymbolClick = useCallback(async (filePath: string) => {
    if (!repositorySnapshot || !activeWorkspaceId) return
    const allFiles = collectEditableFiles(repositorySnapshot)
    const targetFile = allFiles.find(f => f.path === filePath)
    if (targetFile) {
      await openFileFromTree(targetFile)
    }
  }, [repositorySnapshot, activeWorkspaceId, openFileFromTree])


  const statusLabel = editorSaving ? "Saving..." : editorDirty ? "Unsaved" : "Saved"
  const hasEditorContextMismatch = editorWorkspaceId !== activeWorkspaceId || (editorRunId || null) !== (activeRunId || null)

  return (
    <div className="flex h-full min-h-0 bg-[#1e1e1e] text-gray-200 w-full relative">
      <Group orientation="horizontal" className="flex h-full w-full">
        <Panel defaultSize="22%" minSize="15%" maxSize="40%">
          <RepositoryExplorer sidebar={true} onViewChange={onViewChange} />
        </Panel>
        
        <Separator className="w-1 bg-[#2d2d2d] hover:bg-blue-500/50 cursor-col-resize transition-all duration-150 relative select-none" />

        <Panel>
          <div className="flex flex-col min-w-0 h-full overflow-hidden">
          <div className="flex min-h-14 shrink-0 items-center justify-between gap-3 border-b border-[#2d2d2d] bg-[#1e1e1e] px-4">
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-3">
                <Code2 className="h-4 w-4 shrink-0 text-blue-300" />
                <h2 className="truncate text-sm font-semibold text-gray-100">
                  {selectedEditorFile?.name || "No file open"}
                </h2>
                {selectedEditorFile?.language && (
                  <span className="rounded border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] uppercase tracking-widest text-blue-300">
                    {selectedEditorFile.language}
                  </span>
                )}
                {selectedEditorFile && (
                  <span className={`inline-flex h-6 items-center gap-1.5 rounded border px-2 text-[11px] ${
                    editorDirty
                      ? "border-yellow-400/30 bg-yellow-500/10 text-yellow-300"
                      : "border-green-400/30 bg-green-500/10 text-green-300"
                  }`}>
                    {!editorDirty && !editorSaving && <Check className="h-3 w-3" />}
                    {editorSaving && <Loader2 className="h-3 w-3 animate-spin" />}
                    {statusLabel}
                  </span>
                )}
              </div>
              <p className="mt-0.5 truncate text-[11px] text-gray-500">
                {selectedEditorFile?.path || "Open a file from the editor explorer or the Explore view."}
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => onViewChange("explore")}
                className="inline-flex h-8 items-center rounded-md border border-border px-2.5 text-xs font-medium text-gray-300 transition hover:bg-white/5"
              >
                Explore
              </button>
              <button
                type="button"
                onClick={() => void reloadCurrentFile()}
                disabled={!selectedEditorFile || editorSaving || editorReloading || hasEditorContextMismatch}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-border px-2.5 text-xs font-medium text-gray-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {editorReloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                {editorReloading ? "Reloading" : "Reload"}
              </button>
              <button
                type="button"
                onClick={() => void saveCurrentFile()}
                disabled={!selectedEditorFile || !editorDirty || editorSaving || editorReloading || hasEditorContextMismatch}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-blue-400/30 bg-blue-500/10 px-2.5 text-xs font-medium text-blue-100 transition hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {editorSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                {editorSaving ? "Saving" : editorDirty ? "Save" : "Saved"}
              </button>
            </div>
          </div>

          {editorError && (
            <div className="flex shrink-0 items-start gap-2 border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-sm text-red-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{editorError}</span>
            </div>
          )}

          {!selectedEditorFile ? (
            <div className="flex min-h-0 flex-1 items-center justify-center bg-[#1e1e1e] p-8 text-center">
              <div className="max-w-md">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-panel">
                  <Code2 className="h-5 w-5 text-blue-300" />
                </div>
                <h2 className="mt-4 text-lg font-semibold text-gray-100">Open a file to edit</h2>
                <p className="mt-2 text-sm text-gray-400">
                  Use the editor explorer on the left, or open a file from the Explore view.
                </p>
                <button
                  type="button"
                  onClick={() => onViewChange("explore")}
                  className="mt-4 rounded-md border border-border px-3 py-2 text-sm text-gray-200 transition hover:bg-white/5"
                >
                  Go to Explore
                </button>
              </div>
            </div>
          ) : (
            <div className="min-h-0 flex-1 bg-[#1e1e1e]">
              <Editor
                key={`${activeWorkspaceId || "workspace"}:${activeRunId || "run"}:${selectedEditorFile.pathId}`}
                path={`${activeWorkspaceId || "workspace"}/${activeRunId || "run"}/${selectedEditorFile.path}`}
                value={editorContent}
                language={monacoLanguageFromEditorLanguage(selectedEditorFile.language || selectedEditorFile.path)}
                theme="vs-dark"
                loading={
                  <div className="flex h-full items-center justify-center bg-[#1e1e1e] text-xs text-gray-500">
                    Loading editor...
                  </div>
                }
                onChange={(value) => setEditorContent(value ?? "")}
                options={{
                  automaticLayout: true,
                  contextmenu: false,
                  detectIndentation: true,
                  folding: true,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                  fontSize: 14,
                  lineHeight: 24,
                  lineNumbers: "on",
                  minimap: { enabled: false },
                  overviewRulerBorder: false,
                  padding: { top: 16, bottom: 16 },
                  renderLineHighlight: "line",
                  scrollBeyondLastLine: false,
                  tabSize: 2,
                  wordWrap: "off",
                  ariaLabel: `Editing ${selectedEditorFile.path}`,
                }}
              />
            </div>
          )}

          <div className="flex h-7 shrink-0 items-center justify-between border-t border-[#2d2d2d] bg-[#181818] px-3 text-[11px] text-gray-500">
            <div className="min-w-0 truncate">
              {selectedEditorFile
                ? `${selectedEditorFile.path} · ${lineCount} lines`
                : `${editorFiles.length} editable files`}
            </div>
            <div className="shrink-0">
              Ctrl+S to save
            </div>
          </div>
        </div>
      </Panel>

      {selectedEditorFile && (
        <>
          <Separator className="w-1 bg-[#2d2d2d] hover:bg-blue-500/50 cursor-col-resize transition-all duration-150 relative select-none" />
          <Panel defaultSize="25%" minSize="20%" maxSize="40%" collapsible={true}>
            <FileInspector
              file={{
                name: selectedEditorFile.name,
                path: selectedEditorFile.path,
                pathId: selectedEditorFile.pathId,
                type: "file",
              }}
              onSymbolClick={handleSymbolClick}
              onViewChange={onViewChange}
              metadataOnly={true}
            />
          </Panel>
        </>
      )}
      </Group>
    </div>
  )
}

interface EditorFileEntry {
  name: string
  path: string
  pathId: string
  language?: string
}

function collectEditableFiles(snapshot: unknown): EditorFileEntry[] {
  const results = new Map<string, EditorFileEntry>()

  const visit = (node: unknown) => {
    if (!node) return

    if (Array.isArray(node)) {
      node.forEach(visit)
      return
    }

    if (typeof node !== "object") return

    const record = node as Record<string, unknown>

    const children = [
      ...readArray(record.tree),
      ...readArray(record.children),
      ...readArray(record.files),
      ...readArray(record.nodes),
      ...readArray(record.items),
    ]

    const name = readString(record.name)
    const path = normalizePath(
      readString(record.path) ||
      readString(record.relativePath) ||
      readString(record.relative_path) ||
      readString(record.filePath) ||
      readString(record.file_path) ||
      name
    )
    const pathId =
      readString(record.pathId) ||
      readString(record.path_id) ||
      readString(record.fileId) ||
      readString(record.file_id)

    const rawType = String(readString(record.type) || readString(record.kind) || "").toLowerCase()
    const isDirectory =
      rawType.includes("dir") ||
      rawType.includes("folder") ||
      record.isDirectory === true ||
      record.is_directory === true

    if (!isDirectory && name && path && pathId && isLikelyEditableFile(path)) {
      results.set(pathId, {
        name,
        path,
        pathId,
        language: readString(record.language) || languageFromPath(path),
      })
    }

    children.forEach(visit)
  }

  visit(snapshot)

  return Array.from(results.values()).sort((a, b) => a.path.localeCompare(b.path))
}

function readArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function readString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

function normalizePath(path: string): string {
  return path.replace(/\\/g, "/").replace(/^\/+/, "")
}

function languageFromPath(path: string): string {
  const extension = path.split(".").pop()?.toLowerCase()

  if (!extension) return "text"

  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "tsx",
    js: "javascript",
    jsx: "jsx",
    json: "json",
    css: "css",
    html: "html",
    md: "markdown",
    py: "python",
    php: "php",
    yml: "yaml",
    yaml: "yaml",
    env: "env",
  }

  return map[extension] || extension
}

function monacoLanguageFromEditorLanguage(languageOrPath: string): string {
  const normalized = languageOrPath.toLowerCase()
  const extension = normalized.includes(".") ? normalized.split(".").pop() || normalized : normalized

  const map: Record<string, string> = {
    env: "plaintext",
    html: "html",
    css: "css",
    js: "javascript",
    javascript: "javascript",
    jsx: "javascript",
    json: "json",
    md: "markdown",
    markdown: "markdown",
    php: "php",
    py: "python",
    python: "python",
    text: "plaintext",
    ts: "typescript",
    tsx: "typescript",
    typescript: "typescript",
    txt: "plaintext",
    yaml: "yaml",
    yml: "yaml",
  }

  return map[extension] || map[normalized] || "plaintext"
}

function isLikelyEditableFile(path: string): boolean {
  const normalized = normalizePath(path).toLowerCase()

  if (
    normalized.includes("node_modules/") ||
    normalized.includes(".orchestration/") ||
    normalized.includes("dist/") ||
    normalized.includes("build/") ||
    normalized.includes("__pycache__/") ||
    normalized.includes(".git/")
  ) {
    return false
  }

  const editableExtensions = [
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".css",
    ".html",
    ".md",
    ".py",
    ".php",
    ".yml",
    ".yaml",
    ".env",
    ".txt",
  ]

  return editableExtensions.some(extension => normalized.endsWith(extension))
}
