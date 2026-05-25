import { useEffect, useMemo, useState } from "react"
import { Archive, Copy, FolderOpen, Loader2, Pencil, Plus, Search, X } from "lucide-react"
import type { WorkspaceMetadata } from "../stores/workspace.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import {
  archiveWorkspace,
  createWorkspace,
  duplicateWorkspace,
  fetchWorkspaces,
  updateWorkspace,
} from "../api/workspace.api"

type DialogMode = "create" | "rename" | "duplicate" | "archive" | null

export default function WorkspaceLoader() {
  const [projects, setProjects] = useState<WorkspaceMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [workingId, setWorkingId] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState("")
  const [query, setQuery] = useState("")
  const [dialogMode, setDialogMode] = useState<DialogMode>(null)
  const [dialogProject, setDialogProject] = useState<WorkspaceMetadata | null>(null)
  const [projectName, setProjectName] = useState("")

  const bindWorkspace = useWorkspaceStore((s) => s.bindWorkspace)
  const loadWorkspaceData = useWorkspaceStore((s) => s.loadWorkspaceData)

  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return projects
    return projects.filter((project) => {
      return project.name.toLowerCase().includes(needle)
        || project.id.toLowerCase().includes(needle)
        || (project.pathLabel || project.path || "").toLowerCase().includes(needle)
    })
  }, [projects, query])

  useEffect(() => {
    refreshProjects()
  }, [])

  async function refreshProjects() {
    setLoading(true)
    setErrorMsg("")
    try {
      const data = await fetchWorkspaces()
      setProjects(Array.isArray(data) ? data : [])
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Unable to load projects.")
    } finally {
      setLoading(false)
    }
  }

  async function openProject(project: WorkspaceMetadata) {
    setWorkingId(project.id)
    setErrorMsg("")
    try {
      bindWorkspace(project)
      await loadWorkspaceData(project.id)
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Unable to open project.")
    } finally {
      setWorkingId(null)
    }
  }

  function startCreate() {
    setProjectName("")
    setDialogProject(null)
    setDialogMode("create")
  }

  function startRename(project: WorkspaceMetadata) {
    setProjectName(project.name)
    setDialogProject(project)
    setDialogMode("rename")
  }

  function startDuplicate(project: WorkspaceMetadata) {
    setProjectName(`${project.name} Copy`)
    setDialogProject(project)
    setDialogMode("duplicate")
  }

  function startArchive(project: WorkspaceMetadata) {
    setProjectName(project.name)
    setDialogProject(project)
    setDialogMode("archive")
  }

  function closeDialog() {
    setDialogMode(null)
    setDialogProject(null)
    setProjectName("")
  }

  async function submitDialog() {
    if (!dialogMode) return
    setErrorMsg("")
    const targetId = dialogProject?.id || "__new__"
    setWorkingId(targetId)
    try {
      if (dialogMode === "create") {
        const created = await createWorkspace(projectName)
        await refreshProjects()
        closeDialog()
        await openProject(created)
        return
      }
      if (!dialogProject) return
      if (dialogMode === "rename") {
        await updateWorkspace(dialogProject.id, projectName)
      } else if (dialogMode === "duplicate") {
        await duplicateWorkspace(dialogProject.id, projectName)
      } else if (dialogMode === "archive") {
        await archiveWorkspace(dialogProject.id)
      }
      closeDialog()
      await refreshProjects()
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : "Project operation failed.")
    } finally {
      setWorkingId(null)
    }
  }

  const actionLabel = dialogMode === "create"
    ? "Create Project"
    : dialogMode === "rename"
      ? "Rename Project"
      : dialogMode === "duplicate"
        ? "Duplicate Project"
        : "Archive Project"

  return (
    <div className="h-screen w-screen bg-[#111113] text-gray-200 font-sans overflow-hidden">
      <div className="mx-auto flex h-full w-full max-w-6xl flex-col px-6 py-8">
        <header className="flex flex-col gap-5 border-b border-white/10 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal text-white">AI Agent</h1>
            <p className="mt-2 text-sm text-gray-400">
              Create, open, duplicate, or manage local projects.
            </p>
          </div>
          <button
            onClick={startCreate}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-blue-500 px-4 text-sm font-medium text-white transition hover:bg-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-300"
          >
            <Plus className="h-4 w-4" />
            New Project
          </button>
        </header>

        <div className="mt-6 flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search projects"
              className="h-10 w-full rounded-md border border-white/10 bg-[#18181b] pl-10 pr-3 text-sm text-gray-100 outline-none transition placeholder:text-gray-500 focus:border-blue-400"
            />
          </div>
          <button
            onClick={refreshProjects}
            disabled={loading}
            className="h-10 rounded-md border border-white/10 px-4 text-sm text-gray-300 transition hover:bg-white/5 disabled:opacity-50"
          >
            Refresh
          </button>
        </div>

        {errorMsg && (
          <div className="mt-4 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {errorMsg}
          </div>
        )}

        <main className="mt-6 min-h-0 flex-1 overflow-auto rounded-md border border-white/10 bg-[#151518]">
          <div className="grid min-w-[860px] grid-cols-[1.2fr_1fr_120px_260px] gap-4 border-b border-white/10 px-5 py-3 text-xs font-medium uppercase text-gray-500">
            <span>Project</span>
            <span>Path</span>
            <span>Status</span>
            <span className="text-right">Actions</span>
          </div>

          {loading ? (
            <div className="flex h-64 items-center justify-center gap-3 text-sm text-gray-400">
              <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
              Loading projects
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center text-center">
              <FolderOpen className="h-10 w-10 text-gray-600" />
              <div className="mt-4 text-sm font-medium text-gray-300">No projects found</div>
              <div className="mt-1 max-w-sm text-sm text-gray-500">
                Create a local project to start working in the AI Agent workspace.
              </div>
            </div>
          ) : (
            <div className="min-w-[860px] divide-y divide-white/10">
              {filteredProjects.map((project) => (
                <ProjectRow
                  key={project.id}
                  project={project}
                  busy={workingId === project.id}
                  onOpen={() => openProject(project)}
                  onRename={() => startRename(project)}
                  onDuplicate={() => startDuplicate(project)}
                  onArchive={() => startArchive(project)}
                />
              ))}
            </div>
          )}
        </main>
      </div>

      {dialogMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-md rounded-md border border-white/10 bg-[#1c1c20] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-white">{actionLabel}</h2>
                <p className="mt-1 text-sm text-gray-400">
                  {dialogMode === "archive"
                    ? "This moves the project folder into the local project trash."
                    : "Project names become safe local workspace folders."}
                </p>
              </div>
              <button onClick={closeDialog} className="rounded p-1 text-gray-500 hover:bg-white/5 hover:text-gray-200" title="Close">
                <X className="h-4 w-4" />
              </button>
            </div>

            {dialogMode === "archive" ? (
              <div className="mt-5 rounded-md border border-yellow-500/20 bg-yellow-500/10 p-3 text-sm text-yellow-100">
                Archive <span className="font-semibold">{dialogProject?.name}</span>? Active runtimes must be stopped first.
              </div>
            ) : (
              <label className="mt-5 block">
                <span className="text-xs font-medium uppercase text-gray-500">Project name</span>
                <input
                  autoFocus
                  value={projectName}
                  onChange={(event) => setProjectName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") submitDialog()
                    if (event.key === "Escape") closeDialog()
                  }}
                  className="mt-2 h-10 w-full rounded-md border border-white/10 bg-[#111113] px-3 text-sm text-gray-100 outline-none transition focus:border-blue-400"
                />
              </label>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={closeDialog}
                className="h-9 rounded-md border border-white/10 px-4 text-sm text-gray-300 transition hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                onClick={submitDialog}
                disabled={Boolean(workingId) || (dialogMode !== "archive" && projectName.trim().length < 2)}
                className="inline-flex h-9 items-center gap-2 rounded-md bg-blue-500 px-4 text-sm font-medium text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {workingId && <Loader2 className="h-4 w-4 animate-spin" />}
                {actionLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ProjectRow({
  project,
  busy,
  onOpen,
  onRename,
  onDuplicate,
  onArchive,
}: {
  project: WorkspaceMetadata
  busy: boolean
  onOpen: () => void
  onRename: () => void
  onDuplicate: () => void
  onArchive: () => void
}) {
  const status = normalizeStatus(project)
  return (
    <div
      data-testid={`project-row-${project.id}`}
      className={`grid grid-cols-[1.2fr_1fr_120px_260px] items-center gap-4 px-5 py-4 transition hover:bg-white/[0.03] ${busy ? "opacity-60" : ""}`}
    >
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-gray-100">{project.name}</div>
        <div className="mt-1 text-xs text-gray-500">
          Updated {formatDate(project.updatedAt || project.updated_at)}
        </div>
      </div>
      <div className="truncate text-xs text-gray-500">{project.pathLabel || project.path}</div>
      <div>
        <StatusBadge status={status} />
      </div>
      <div className="flex justify-end gap-2">
        <button data-testid={`project-open-${project.id}`} onClick={onOpen} disabled={busy} className="inline-flex h-8 items-center gap-2 rounded-md border border-white/10 px-3 text-xs text-gray-200 transition hover:bg-white/5 disabled:opacity-50" title="Open project">
          <FolderOpen className="h-4 w-4" />
          <span>Open</span>
        </button>
        <button data-testid={`project-rename-${project.id}`} onClick={onRename} disabled={busy} className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-white/10 text-gray-300 transition hover:bg-white/5 disabled:opacity-50" title="Rename project">
          <Pencil className="h-4 w-4" />
        </button>
        <button data-testid={`project-duplicate-${project.id}`} onClick={onDuplicate} disabled={busy} className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-white/10 text-gray-300 transition hover:bg-white/5 disabled:opacity-50" title="Duplicate project">
          <Copy className="h-4 w-4" />
        </button>
        <button data-testid={`project-archive-${project.id}`} onClick={onArchive} disabled={busy} className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-white/10 text-red-300 transition hover:border-red-400/40 hover:bg-red-500/10 disabled:opacity-50" title="Archive project">
          <Archive className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const tone = status === "running"
    ? "border-green-400/30 bg-green-500/10 text-green-300"
    : status === "failed"
      ? "border-red-400/30 bg-red-500/10 text-red-300"
      : status === "stopped" || status === "ready"
        ? "border-blue-400/30 bg-blue-500/10 text-blue-300"
        : "border-gray-500/30 bg-gray-500/10 text-gray-300"
  return (
    <span className={`inline-flex h-7 items-center rounded-full border px-3 text-xs font-medium capitalize ${tone}`}>
      {status}
    </span>
  )
}

function normalizeStatus(project: WorkspaceMetadata): string {
  const runtimeStatus = project.runtime_status?.status
  if (runtimeStatus === "running" || runtimeStatus === "failed" || runtimeStatus === "stopped") return runtimeStatus
  return project.status || "ready"
}

function formatDate(value?: number) {
  if (!value || !Number.isFinite(Number(value))) return "unknown"
  return new Date(Number(value)).toLocaleString()
}
