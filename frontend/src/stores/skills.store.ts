import { create } from 'zustand'

export interface SkillMeta {
  name: string
  type: string
  language: string
  capabilities: string[]
  tags: string[]
  description: string
}

interface SkillsStore {
  skills: SkillMeta[]
  activeSkill: string | null
  enabled: Record<string, boolean>
  setSkills: (skills: SkillMeta[]) => void
  setActiveSkill: (name: string | null) => void
  toggleSkill: (name: string) => void
  isEnabled: (name: string) => boolean
}

export const useSkillsStore = create<SkillsStore>((set, get) => ({
  skills: [],
  activeSkill: null,
  enabled: {},
  setSkills: (skills) => {
    const enabled: Record<string, boolean> = {}
    skills.forEach((s) => { enabled[s.name] = true })
    set({ skills, enabled })
  },
  setActiveSkill: (name) => set({ activeSkill: name }),
  toggleSkill: (name) => set((state) => ({
    enabled: { ...state.enabled, [name]: !state.enabled[name] }
  })),
  isEnabled: (name) => get().enabled[name] !== false,
}))
