import { create } from 'zustand'

export type AgentState =
  | "idle"
  | "planning"
  | "scaffolding"
  | "generating"
  | "writing"
  | "installing"
  | "building"
  | "repairing"
  | "starting_preview"
  | "launching"
  | "preview_ready"
  | "success"
  | "failed"

interface AgentActivity {
  id: string
  message: string
  timestamp: number
}

interface AgentStore {
  state: AgentState
  setState: (state: AgentState) => void
  logs: string[]
  addLog: (log: string) => void
  activities: AgentActivity[]
  addActivity: (message: string) => void
  startTime: number | null
  setStartTime: (time: number | null) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  state: 'idle',
  setState: (state) => set({ state }),
  logs: [],
  addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
  activities: [],
  addActivity: (message) => set((state) => ({ 
    activities: [...state.activities, { id: Math.random().toString(36).substr(2, 9), message, timestamp: Date.now() }] 
  })),
  startTime: null,
  setStartTime: (time) => set({ startTime: time })
}))
