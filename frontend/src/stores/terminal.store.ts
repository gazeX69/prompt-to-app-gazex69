import { create } from 'zustand'

export interface TerminalLine {
  id: string
  text: string
  type: 'stdout' | 'stderr' | 'info'
}

interface TerminalStore {
  lines: TerminalLine[]
  addLine: (line: Omit<TerminalLine, 'id'>) => void
  clear: () => void
}

export const useTerminalStore = create<TerminalStore>((set) => ({
  lines: [
    { id: '1', text: 'AI Coding Agent Terminal initialized.', type: 'info' }
  ],
  addLine: (line) => set((state) => ({ 
    lines: [...state.lines, { ...line, id: Math.random().toString(36).substring(7) }] 
  })),
  clear: () => set({ lines: [] }),
}))
