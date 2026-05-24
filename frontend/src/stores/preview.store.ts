import { create } from 'zustand'

interface PreviewStore {
  url: string | null
  runId: string | null
  setUrl: (url: string | null, runId?: string | null) => void
  isReloading: boolean
  setReloading: (val: boolean) => void
}

export const usePreviewStore = create<PreviewStore>((set) => ({
  url: null,
  runId: null,
  setUrl: (url, runId = null) => set({ url, runId }),
  isReloading: false,
  setReloading: (isReloading) => set({ isReloading }),
}))
