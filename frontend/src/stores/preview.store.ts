import { create } from 'zustand'

interface PreviewStore {
  url: string | null
  setUrl: (url: string | null) => void
  isReloading: boolean
  setReloading: (val: boolean) => void
}

export const usePreviewStore = create<PreviewStore>((set) => ({
  url: null,
  setUrl: (url) => set({ url }),
  isReloading: false,
  setReloading: (isReloading) => set({ isReloading }),
}))
