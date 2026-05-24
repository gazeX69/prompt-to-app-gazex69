import { useSkillsStore } from '../stores/skills.store'
import { CheckCircle2, Circle, Code2, Box, Wrench } from 'lucide-react'

function typeIcon(type: string) {
  switch (type) {
    case 'framework': return <Code2 className="w-4 h-4" />
    case 'language': return <Box className="w-4 h-4" />
    default: return <Wrench className="w-4 h-4" />
  }
}

export default function SkillsPanel() {
  const { skills, enabled, toggleSkill } = useSkillsStore()

  return (
    <div className="h-full flex flex-col bg-panel/50">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-gray-200">AI Skills</h2>
        <p className="text-[11px] text-gray-500 mt-0.5">Modular capability plugins</p>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {skills.length === 0 && (
          <div className="text-[12px] text-gray-600 italic text-center py-8">
            No skills registered. Start a generation to load skills.
          </div>
        )}

        {skills.map((skill) => {
          const active = enabled[skill.name] !== false
          return (
            <div
              key={skill.name}
              className={`rounded-lg border ${
                active ? 'border-border bg-background' : 'border-border/50 bg-background/50 opacity-60'
              } p-3 transition-all`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">{typeIcon(skill.type)}</span>
                  <span className="text-[13px] font-medium text-gray-200">{skill.name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 uppercase font-semibold">
                    {skill.language}
                  </span>
                </div>
                <button
                  onClick={() => toggleSkill(skill.name)}
                  className="focus:outline-none"
                >
                  {active
                    ? <CheckCircle2 className="w-4 h-4 text-green-500" />
                    : <Circle className="w-4 h-4 text-gray-600" />
                  }
                </button>
              </div>
              <p className="text-[11px] text-gray-500 mb-2">{skill.description}</p>
              <div className="flex flex-wrap gap-1">
                {skill.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400"
                  >
                    {cap}
                  </span>
                ))}
                {skill.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800/50 text-gray-500"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
