import { create } from 'zustand'

export interface RuntimeStatusSnapshot {
  project_id: string | null
  run_id: string | null
  status: string
  port: number | null
  pid: number | null
  url: string | null
  started_at: number | null
  last_healthcheck: number | null
  error: string | null
}

export interface GenerationFailureSnapshot {
  project_id: string | null
  run_id: string | null
  stage: string
  message: string
  timestamp: number | null
}

export interface GenerationStatusSnapshot {
  project_id: string | null
  generation_id: string | null
  status: 'accepted' | 'generating' | 'succeeded' | 'failed' | 'unknown' | string
  phase: string
  message: string
  detail: Record<string, unknown>
  created_at: number | null
  updated_at: number | null
  runtime_run_id: string | null
  runtime_url: string | null
  runtime_port: number | null
}

interface PreviewStore {
  url: string | null
  runId: string | null
  runtimeStatus: RuntimeStatusSnapshot | null
  generationFailure: GenerationFailureSnapshot | null
  generationStatus: GenerationStatusSnapshot | null
  refreshToken: number
  setUrl: (url: string | null, runId?: string | null) => void
  setRuntimeStatus: (runtimeStatus: RuntimeStatusSnapshot | null) => void
  setGenerationFailure: (generationFailure: GenerationFailureSnapshot | null) => void
  setGenerationStatus: (generationStatus: GenerationStatusSnapshot | null) => void
  clear: () => void
  hardRefresh: () => void
  isReloading: boolean
  setReloading: (val: boolean) => void
}

export const usePreviewStore = create<PreviewStore>((set) => ({
  url: null,
  runId: null,
  runtimeStatus: null,
  generationFailure: null,
  generationStatus: null,
  refreshToken: 0,
  setUrl: (url, runId = null) => set((state) => ({
    url,
    runId,
    generationFailure: null,
    refreshToken: state.refreshToken + 1,
  })),
  setRuntimeStatus: (runtimeStatus) => set({ runtimeStatus }),
  setGenerationFailure: (generationFailure) => set({ generationFailure }),
  setGenerationStatus: (generationStatus) => set({ generationStatus }),
  clear: () => set((state) => ({
    url: null,
    runId: null,
    refreshToken: state.refreshToken + 1,
  })),
  hardRefresh: () => set((state) => ({ refreshToken: state.refreshToken + 1 })),
  isReloading: false,
  setReloading: (isReloading) => set({ isReloading }),
}))
