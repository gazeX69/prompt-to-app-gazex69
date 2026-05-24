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

interface PreviewStore {
  url: string | null
  runId: string | null
  runtimeStatus: RuntimeStatusSnapshot | null
  refreshToken: number
  setUrl: (url: string | null, runId?: string | null) => void
  setRuntimeStatus: (runtimeStatus: RuntimeStatusSnapshot | null) => void
  clear: () => void
  hardRefresh: () => void
  isReloading: boolean
  setReloading: (val: boolean) => void
}

export const usePreviewStore = create<PreviewStore>((set) => ({
  url: null,
  runId: null,
  runtimeStatus: null,
  refreshToken: 0,
  setUrl: (url, runId = null) => set((state) => ({
    url,
    runId,
    refreshToken: state.refreshToken + 1,
  })),
  setRuntimeStatus: (runtimeStatus) => set({ runtimeStatus }),
  clear: () => set((state) => ({
    url: null,
    runId: null,
    refreshToken: state.refreshToken + 1,
  })),
  hardRefresh: () => set((state) => ({ refreshToken: state.refreshToken + 1 })),
  isReloading: false,
  setReloading: (isReloading) => set({ isReloading }),
}))
