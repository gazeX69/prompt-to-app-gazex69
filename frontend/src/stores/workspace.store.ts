import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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
  status: 'success' | 'failure' | 'running'
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

export type WorkspaceHydrationStatus = 'idle' | 'loading' | 'ready' | 'error'

function asArray<T>(value: T[] | unknown): T[] {
  return Array.isArray(value) ? value : []
}

interface WorkspaceStore {
  
  // Identity
  activeWorkspaceId: string | null
  
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
  
  // Actions
  bindWorkspace: (workspace: WorkspaceMetadata) => void
  closeWorkspace: () => void
  addRunToHistory: (run: RunMetadata) => void
  setActiveRun: (runId: string | null) => void
  hydrateWorkspace: (repo: RepositorySnapshot, runtime: WorkspaceRuntimeSnapshot, artifacts: ArtifactSnapshot[]) => void
  loadWorkspaceData: (workspaceId: string) => Promise<void>
  ensureWorkspaceHydrated: (workspaceId?: string | null) => Promise<void>
  loadRunData: (workspaceId: string, runId: string) => Promise<void>
  openFileInEditor: (file: EditorFileMetadata, content: string, workspaceId: string, runId?: string | null) => void
  setEditorContent: (content: string) => void
  setEditorSaving: (saving: boolean) => void
  setEditorError: (error: string | null) => void
  markEditorSaved: (content: string) => void
  clearEditorState: () => void
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

export const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set) => ({
      activeWorkspaceId: null,
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

          const [tree, artifacts, runs] = await Promise.all([
            fetchWorkspaceTree(workspaceId),
            fetchArtifacts(workspaceId).catch(() => []),
            fetchWorkspaceRuns(workspaceId).catch(() => [])
          ])

          set(() => ({
            activeWorkspaceId: workspaceId,
            repositorySnapshot: tree,
            artifactSnapshots: asArray<ArtifactSnapshot>(artifacts),
            runHistory: asArray<RunMetadata>(runs),
            activeRunId: asArray<RunMetadata>(runs)[0]?.run_id || null,
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
            activeRunId: runId
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

      clearEditorState: () => set(emptyEditorState)
    }),
    {
      name: 'workspace-storage',
      partialize: (state) => ({
        activeWorkspaceId: state.activeWorkspaceId,
        workspaces: state.workspaces,
        recentWorkspaces: state.recentWorkspaces,
        
      })

    }
  )
)
