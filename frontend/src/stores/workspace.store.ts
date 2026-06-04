import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { selectActiveRunId, selectHydrationRunId } from '../stateConsistency'

export interface RepositoryFileNode {
  path: string
  pathId?: string
  name: string
  type: 'file' | 'directory'
  children?: RepositoryFileNode[]
  isEntrypoint?: boolean
  ownershipLabel?: string
  mutationHeat?: 'low' | 'medium' | 'high'
  referencedByCount?: number
}

export interface RepositorySnapshot {
  tree: RepositoryFileNode[]
  ecosystem: string
  totalFiles: number
  runId?: string | null
}

export interface WorkspaceRuntimeSnapshot {
  sequencingStabilityScore: number
  topologyAlignmentScore: number
  mutationLocalityScore: number
  orchestrationHealth: 'healthy' | 'degraded' | 'offline'
}

export interface ArtifactSnapshot {
  id: string
  fileName: string
  relativePath: string
  sizeBytes: number
  category: string
  updatedAt: number
}

export interface WorkspaceMetadata {
  id: string
  name: string
  path?: string
  pathLabel: string
  ecosystem: string
  createdAt: number
  updatedAt: number
  created_at?: number
  updated_at?: number
  runCount: number
  latestRunId?: string
  status?: 'ready' | 'running' | 'failed' | 'stopped' | 'unknown' | 'archived' | string
  runtime_status?: {
    status?: string
    run_id?: string | null
    port?: number | null
    url?: string | null
    error?: string | null
  }
  runtimeHealth: 'healthy' | 'degraded' | 'offline'
  is_archived?: boolean
}

export interface RunMetadata {
  id: string
  run_id: string
  path: string
  prompt: string
  status: 'success' | 'succeeded' | 'failure' | 'failed' | 'running' | string
  active?: boolean
  createdAt: number
  updatedAt: number
  startedAt: number
  durationMs: number
  ecosystem: string
  hasArtifacts: boolean
  artifactCount: number
  topologyScore?: number
  sequencingScore?: number
  costSummary?: unknown
}

export interface EditorFileMetadata {
  name: string
  path: string
  pathId: string
  language?: string
}

export type WorkspaceMode = "generate" | "explore" | "edit" | "preview" | "overview" | "artifacts" | "history" | "terminal" | "skills" | "debug" | "settings"


export interface ExplorerSelectionMetadata {
  name: string
  path: string
  pathId?: string
  type: 'file' | 'directory'
}

export type WorkspaceHydrationStatus = 'idle' | 'loading' | 'ready' | 'error'

function asArray<T>(value: T[] | unknown): T[] {
  return Array.isArray(value) ? value : []
}

interface WorkspaceStore {
  
  // Identity
  activeWorkspaceId: string | null
  activeWorkspaceMode: WorkspaceMode
  
  // Registry
  workspaces: Record<string, WorkspaceMetadata>
  recentWorkspaces: string[] // ordered workspace_ids
  
  // Active Workspace Data
  activeRunId: string | null
  runHistory: RunMetadata[]
  
  // Hydrated Live Data (NOT Persisted)
  repositorySnapshot: RepositorySnapshot | null
  runtimeSnapshot: WorkspaceRuntimeSnapshot | null
  artifactSnapshots: ArtifactSnapshot[]

  workspaceHydrationStatus: WorkspaceHydrationStatus
  workspaceHydrationError: string | null
  hydratingWorkspaceId: string | null

  // Embedded Editor
  selectedEditorFile: EditorFileMetadata | null
  editorWorkspaceId: string | null
  editorRunId: string | null
  editorContent: string
  editorOriginalContent: string
  editorDirty: boolean
  editorSaving: boolean
  editorError: string | null

  // Explorer UI
  selectedExplorerNode: ExplorerSelectionMetadata | null
  explorerSelectionWorkspaceId: string | null
  explorerSelectionRunId: string | null
  explorerCollapsedFolderPaths: string[]
  explorerCollapseWorkspaceId: string | null
  explorerCollapseRunId: string | null
  
  // Actions
  bindWorkspace: (workspace: WorkspaceMetadata) => void
  closeWorkspace: () => void
  setActiveWorkspaceMode: (mode: WorkspaceMode) => void
  addRunToHistory: (run: RunMetadata) => void
  setActiveRun: (runId: string | null) => void
  hydrateWorkspace: (repo: RepositorySnapshot, runtime: WorkspaceRuntimeSnapshot, artifacts: ArtifactSnapshot[]) => void
  loadWorkspaceData: (workspaceId: string) => Promise<void>
  loadWorkspaceRuns: (workspaceId: string) => Promise<void>
  ensureWorkspaceHydrated: (workspaceId?: string | null) => Promise<void>
  loadRunData: (workspaceId: string, runId: string) => Promise<void>
  openFileInEditor: (file: EditorFileMetadata, content: string, workspaceId: string, runId?: string | null) => void
  updateEditorFileMetadata: (file: EditorFileMetadata, workspaceId: string, runId?: string | null) => void
  setEditorContent: (content: string) => void
  setEditorSaving: (saving: boolean) => void
  setEditorError: (error: string | null) => void
  markEditorSaved: (content: string) => void
  clearEditorState: () => void
  selectExplorerNode: (node: ExplorerSelectionMetadata, workspaceId: string, runId?: string | null) => void
  clearExplorerSelection: () => void
  toggleExplorerFolder: (path: string, workspaceId: string, runId?: string | null) => void
}

const emptyEditorState = {
  selectedEditorFile: null,
  editorWorkspaceId: null,
  editorRunId: null,
  editorContent: "",
  editorOriginalContent: "",
  editorDirty: false,
  editorSaving: false,
  editorError: null,
}

const emptyExplorerState = {
  selectedExplorerNode: null,
  explorerSelectionWorkspaceId: null,
  explorerSelectionRunId: null,
  explorerCollapsedFolderPaths: [],
  explorerCollapseWorkspaceId: null,
  explorerCollapseRunId: null,
}

export const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set) => ({
      activeWorkspaceId: null,
      activeWorkspaceMode: 'generate',
      workspaces: {},
      recentWorkspaces: [],
      activeRunId: null,
      runHistory: [],
      
      repositorySnapshot: null,
      runtimeSnapshot: null,
      artifactSnapshots: [],
      workspaceHydrationStatus: 'idle',
      workspaceHydrationError: null,
      hydratingWorkspaceId: null,
      ...emptyEditorState,
      ...emptyExplorerState,

      bindWorkspace: (ws) => set((state) => {
        const updatedWorkspaces = { ...state.workspaces, [ws.id]: ws }
        const recentWorkspaces = asArray<string>(state.recentWorkspaces)
        const recent = [ws.id, ...recentWorkspaces.filter(id => id !== ws.id)]
        return {
          activeWorkspaceId: ws.id,
          workspaces: updatedWorkspaces,
          recentWorkspaces: recent.slice(0, 5),
          repositorySnapshot: null,
          runtimeSnapshot: null,
          artifactSnapshots: [],
          workspaceHydrationStatus: 'idle',
          workspaceHydrationError: null,
          hydratingWorkspaceId: null,
          ...emptyEditorState
        }
      }),
      
      closeWorkspace: () => set({ 
        activeWorkspaceId: null, 
        activeRunId: null, 
        runHistory: [],
        repositorySnapshot: null,
        runtimeSnapshot: null,
        artifactSnapshots: [],
        workspaceHydrationStatus: 'idle',
        workspaceHydrationError: null,
        hydratingWorkspaceId: null,
        ...emptyEditorState
      }),

      setActiveWorkspaceMode: (mode) => set({ activeWorkspaceMode: mode }),
      
      addRunToHistory: (run) => set((state) => ({
        runHistory: [run, ...asArray<RunMetadata>(state.runHistory)]
      })),

      setActiveRun: (runId) => set({ activeRunId: runId }),
      
      hydrateWorkspace: (repo, runtime, artifacts) => set({
        repositorySnapshot: repo,
        runtimeSnapshot: runtime,
        artifactSnapshots: asArray<ArtifactSnapshot>(artifacts),
        workspaceHydrationStatus: 'ready',
        workspaceHydrationError: null,
        hydratingWorkspaceId: null,
      }),

      loadWorkspaceData: async (workspaceId: string) => {
        set({
          workspaceHydrationStatus: 'loading',
          workspaceHydrationError: null,
          hydratingWorkspaceId: workspaceId,
        })

        try {
          const { fetchWorkspaceTree, fetchArtifacts, fetchWorkspaceRuns } = await import('../api/workspace.api')

          const safeRuns = asArray<RunMetadata>(await fetchWorkspaceRuns(workspaceId).catch(() => []))
          const activeRunId = selectHydrationRunId(safeRuns, useWorkspaceStore.getState().activeRunId)
          const [tree, artifacts] = await Promise.all([
            fetchWorkspaceTree(workspaceId, activeRunId || undefined),
            fetchArtifacts(workspaceId, activeRunId || undefined).catch(() => []),
          ])

          set(() => ({
            activeWorkspaceId: workspaceId,
            repositorySnapshot: tree,
            artifactSnapshots: asArray<ArtifactSnapshot>(artifacts),
            runHistory: safeRuns,
            activeRunId: tree.runId || activeRunId,
            runtimeSnapshot: {
              orchestrationHealth: 'healthy',
              sequencingStabilityScore: 9.8,
              topologyAlignmentScore: 10.0,
              mutationLocalityScore: 8.5
            },
            workspaceHydrationStatus: 'ready',
            workspaceHydrationError: null,
            hydratingWorkspaceId: null,
          }))
        } catch (e) {
          const message = e instanceof Error ? e.message : 'Failed to load workspace data'

          console.error("Failed to load workspace data:", e)

          set({
            workspaceHydrationStatus: 'error',
            workspaceHydrationError: message,
            hydratingWorkspaceId: null,
            repositorySnapshot: null,
            runtimeSnapshot: null,
            artifactSnapshots: [],
          })
        }
      },

      loadWorkspaceRuns: async (workspaceId: string) => {
        try {
          const { fetchWorkspaceRuns } = await import('../api/workspace.api')
          const runs = asArray<RunMetadata>(await fetchWorkspaceRuns(workspaceId).catch(() => []))
          const activeRunId = selectActiveRunId(runs)
          set((state) => ({
            runHistory: runs,
            activeRunId: activeRunId || state.activeRunId,
          }))
        } catch (e) {
          console.error("Failed to load workspace runs:", e)
        }
      },

      ensureWorkspaceHydrated: async (workspaceId?: string | null) => {
        const state = useWorkspaceStore.getState()
        const targetWorkspaceId = workspaceId ?? state.activeWorkspaceId

        if (!targetWorkspaceId) return

        const isAlreadyHydratingSameWorkspace =
          state.workspaceHydrationStatus === 'loading' &&
          state.hydratingWorkspaceId === targetWorkspaceId

        if (isAlreadyHydratingSameWorkspace) return

        const alreadyHasRepository =
          state.activeWorkspaceId === targetWorkspaceId &&
          state.repositorySnapshot !== null

        if (alreadyHasRepository) {
          set({
            workspaceHydrationStatus: 'ready',
            workspaceHydrationError: null,
            hydratingWorkspaceId: null,
          })
          return
        }

        await useWorkspaceStore.getState().loadWorkspaceData(targetWorkspaceId)
      },

      loadRunData: async (workspaceId: string, runId: string) => {
        try {
          const { fetchWorkspaceTree, fetchArtifacts } = await import('../api/workspace.api')
          const [tree, artifacts] = await Promise.all([
            fetchWorkspaceTree(workspaceId, runId).catch(() => null),
            fetchArtifacts(workspaceId, runId).catch(() => [])
          ])

          set(() => ({
            repositorySnapshot: tree,
            artifactSnapshots: asArray<ArtifactSnapshot>(artifacts),
            activeRunId: tree?.runId || runId
          }))
        } catch (e) {
          console.error("Failed to load run data:", e)
        }
      },

      openFileInEditor: (file, content, workspaceId, runId = null) => set({
        selectedEditorFile: {
          name: file.name,
          path: file.path,
          pathId: file.pathId,
          language: file.language,
        },
        editorWorkspaceId: workspaceId,
        editorRunId: runId,
        editorContent: content,
        editorOriginalContent: content,
        editorDirty: false,
        editorSaving: false,
        editorError: null,
      }),

      updateEditorFileMetadata: (file, workspaceId, runId = null) => set((state) => {
        if (!state.selectedEditorFile) return {}
        if (state.editorWorkspaceId !== workspaceId) return {}
        if ((state.editorRunId || null) !== (runId || null)) return {}
        return {
          selectedEditorFile: {
            name: file.name,
            path: file.path,
            pathId: file.pathId,
            language: file.language,
          },
          editorError: null,
        }
      }),

      setEditorContent: (content) => set((state) => ({
        editorContent: content,
        editorDirty: content !== state.editorOriginalContent,
        editorError: null,
      })),

      setEditorSaving: (saving) => set({ editorSaving: saving }),
      setEditorError: (error) => set({ editorError: error }),

      markEditorSaved: (content) => set({
        editorContent: content,
        editorOriginalContent: content,
        editorDirty: false,
        editorSaving: false,
        editorError: null,
      }),

      clearEditorState: () => set(emptyEditorState),

      selectExplorerNode: (node, workspaceId, runId = null) => set({
        selectedExplorerNode: {
          name: node.name,
          path: node.path,
          pathId: node.pathId,
          type: node.type,
        },
        explorerSelectionWorkspaceId: workspaceId,
        explorerSelectionRunId: runId || null,
      }),

      clearExplorerSelection: () => set({
        selectedExplorerNode: null,
        explorerSelectionWorkspaceId: null,
        explorerSelectionRunId: null,
      }),

      toggleExplorerFolder: (path, workspaceId, runId = null) => set((state) => {
        const sameTree =
          state.explorerCollapseWorkspaceId === workspaceId &&
          (state.explorerCollapseRunId || null) === (runId || null)
        const current = sameTree ? asArray<string>(state.explorerCollapsedFolderPaths) : []
        const next = current.includes(path)
          ? current.filter(folderPath => folderPath !== path)
          : [...current, path]

        return {
          explorerCollapsedFolderPaths: next,
          explorerCollapseWorkspaceId: workspaceId,
          explorerCollapseRunId: runId || null,
        }
      })
    }),
    {
      name: 'workspace-storage',
      partialize: (state) => ({
        activeWorkspaceId: state.activeWorkspaceId,
        activeWorkspaceMode: state.activeWorkspaceMode,
        workspaces: state.workspaces,
        recentWorkspaces: state.recentWorkspaces,
        selectedEditorFile: state.selectedEditorFile,
        editorWorkspaceId: state.editorWorkspaceId,
        editorRunId: state.editorRunId,
        selectedExplorerNode: state.selectedExplorerNode,
        explorerSelectionWorkspaceId: state.explorerSelectionWorkspaceId,
        explorerSelectionRunId: state.explorerSelectionRunId,
        explorerCollapsedFolderPaths: state.explorerCollapsedFolderPaths,
        explorerCollapseWorkspaceId: state.explorerCollapseWorkspaceId,
        explorerCollapseRunId: state.explorerCollapseRunId,
      })

    }
  )
)
