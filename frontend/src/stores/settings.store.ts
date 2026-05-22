import { create } from 'zustand'

interface SettingsStore {
  theme: 'dark' | 'light'
  setTheme: (theme: 'dark' | 'light') => void
}

export const useSettingsStore = create<SettingsStore>((set) => ({
  theme: 'dark',
  setTheme: (theme) => set({ theme }),
}))
