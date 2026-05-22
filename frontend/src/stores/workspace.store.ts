import { create } from 'zustand'

interface WorkspaceStore {
  activeProject: string | null
  setActiveProject: (project: string | null) => void
}

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  activeProject: null,
  setActiveProject: (activeProject) => set({ activeProject }),
}))
