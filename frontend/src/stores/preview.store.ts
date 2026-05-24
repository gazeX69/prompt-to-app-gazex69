import { create } from 'zustand'

interface PreviewStore {
  url: string | null
  runId: string | null
  refreshToken: number
  setUrl: (url: string | null, runId?: string | null) => void
  clear: () => void
  hardRefresh: () => void
  isReloading: boolean
  setReloading: (val: boolean) => void
}

export const usePreviewStore = create<PreviewStore>((set) => ({
  url: null,
  runId: null,
  refreshToken: 0,
  setUrl: (url, runId = null) => set((state) => ({
    url,
    runId,
    refreshToken: state.refreshToken + 1,
  })),
  clear: () => set((state) => ({
    url: null,
    runId: null,
    refreshToken: state.refreshToken + 1,
  })),
  hardRefresh: () => set((state) => ({ refreshToken: state.refreshToken + 1 })),
  isReloading: false,
  setReloading: (isReloading) => set({ isReloading }),
}))
