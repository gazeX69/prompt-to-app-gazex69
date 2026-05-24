import { create } from 'zustand'
import { type ExecutionState, type RuntimeExecutionState, type RuntimeLifecycleEvent, type StructuredRuntimeError, isTerminalExecutionState, mapRuntimeLifecycleToState, normalizeExecutionState } from '../runtime/executionContract'

export type AgentState = ExecutionState

export function isTerminalState(state: AgentState): boolean {
  return isTerminalExecutionState(state)
}

export function isLoadingState(state: AgentState): boolean {
  return !isTerminalState(state) && state !== 'IDLE'
}

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
  lastRuntimeError: StructuredRuntimeError | null
  setRuntimeError: (error: StructuredRuntimeError) => void
  latestRuntimeLifecycleEvent: RuntimeLifecycleEvent | null
  setRuntimeLifecycleEvent: (event: RuntimeLifecycleEvent) => void
  runtimeState: RuntimeExecutionState
  setRuntimeState: (state: RuntimeExecutionState) => void
  startTime: number | null
  setStartTime: (time: number | null) => void
  socketConnected: boolean
  setSocketConnected: (connected: boolean) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  state: 'IDLE',
  setState: (state) => set({ state: normalizeExecutionState(state) }),
  logs: [],
  addLog: (log) => set((state) => ({ logs: [...state.logs, log] })),
  activities: [],
  addActivity: (message) => set((state) => ({
    activities: [...state.activities, { id: Math.random().toString(36).substr(2, 9), message, timestamp: Date.now() }]
  })),
  lastRuntimeError: null,
  setRuntimeError: (error) => set({ lastRuntimeError: error }),
  latestRuntimeLifecycleEvent: null,
  setRuntimeLifecycleEvent: (event) => set({
    latestRuntimeLifecycleEvent: event,
    runtimeState: mapRuntimeLifecycleToState(event),
  }),
  runtimeState: 'IDLE',
  setRuntimeState: (state) => set({ runtimeState: state }),
  startTime: null,
  setStartTime: (time) => set({ startTime: time }),
  socketConnected: false,
  setSocketConnected: (connected) => {
    set((state) => {
      if (connected) {
        if (state.state === 'DISCONNECTED' || state.state === 'RECONNECTING') {
          return { socketConnected: true, state: 'IDLE' }
        }
        return { socketConnected: true }
      } else {
        if (state.state === 'IDLE' || isTerminalState(state.state)) {
          return { socketConnected: false }
        }
        return { socketConnected: false, state: 'RECONNECTING' }
      }
    })
  },
}))
