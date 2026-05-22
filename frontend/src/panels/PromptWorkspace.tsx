import { useState } from 'react'
import { Send, Wrench, ChevronDown, AlignLeft } from 'lucide-react'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from "../stores/terminal.store"
import { api } from "../services/api"
import { ProgressView } from "./ProgressView"

export default function PromptWorkspace() {
  const [prompt, setPrompt] = useState('')
  const [autoRepair, setAutoRepair] = useState(true)
  const { state, setState: setAgentState, setStartTime } = useAgentStore()
  
  const handleGenerate = async () => {
    if (!prompt.trim()) return
    
    useTerminalStore.getState().clear()
    setStartTime(Date.now())
    setAgentState('generating')
    useAgentStore.setState({ activities: [] }) // clear old activities
    
    try {
      await api.post("/generate", {
        prompt: prompt,
        project_id: `proj-${Date.now()}`,
        project_type: 'react',
        auto_repair: autoRepair,
        max_repair_attempts: 3
      })
    } catch (err) {
      console.error('Failed to start generation:', err)
      setAgentState('failed')
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 p-4 md:p-8 overflow-y-auto">
      <div className="max-w-4xl w-full mx-auto flex-1 flex flex-col justify-end pb-4">
        
        {/* Main Content Area */}
        {state === 'idle' ? (
          <div className="flex-1 flex flex-col justify-center items-center text-center opacity-50 mb-12 min-h-[120px]">
             <AlignLeft className="w-8 h-8 mb-4 text-gray-500" />
             <h2 className="text-lg font-medium text-gray-200">What are we building?</h2>
             <p className="text-[13px] text-gray-400 mt-2 max-w-sm">
               Describe your project layout, features, and dependencies.
             </p>
          </div>
        ) : (
          <div className="flex-1 mb-8 overflow-y-auto">
            <ProgressView />
          </div>
        )}

        {/* Prompt Input Container */}
        <div className="bg-panel rounded-xl border border-border shadow-sm flex flex-col focus-within:border-gray-500 transition-colors overflow-hidden shrink-0">
          <textarea
            className="w-full bg-transparent border-none px-4 py-4 text-[14px] text-gray-200 placeholder:text-gray-500 focus:outline-none resize-none leading-relaxed"
            rows={4}
            placeholder="Build a modern dashboard with React and Tailwind..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                handleGenerate()
              }
            }}
          />
          
          <div className="flex items-center justify-between px-3 py-2 border-t border-border/50 bg-background/50">
            <div className="flex items-center space-x-2">
              <button className="flex items-center text-[12px] font-medium text-gray-400 hover:text-gray-200 transition-colors bg-accent/50 px-2.5 py-1.5 rounded-md border border-border/50">
                React + Tailwind
                <ChevronDown className="w-3.5 h-3.5 ml-1.5 opacity-70" />
              </button>
              
              <label className="flex items-center cursor-pointer text-[12px] font-medium text-gray-400 hover:text-gray-200 transition-colors px-2 py-1.5">
                <input 
                  type="checkbox" 
                  className="mr-2 rounded bg-accent border-border focus:ring-0"
                  checked={autoRepair}
                  onChange={(e) => setAutoRepair(e.target.checked)}
                />
                <Wrench className="w-3 h-3 mr-1.5" />
                Auto-repair
              </label>
            </div>
            
            <button 
              onClick={handleGenerate}
              disabled={!prompt.trim() || (state !== 'idle' && state !== 'failed' && state !== 'success')}
              className="bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white text-black font-medium text-[12px] px-4 py-1.5 rounded-md flex items-center transition-colors"
            >
              <Send className="w-3.5 h-3.5 mr-2" />
              Generate
            </button>
          </div>
        </div>
        
        <div className="mt-4 flex flex-wrap gap-2 justify-center">
          <TemplatePill text="Blog with Next.js" />
          <TemplatePill text="FastAPI backend" />
          <TemplatePill text="Weather app" />
        </div>
      </div>
    </div>
  )
}

function TemplatePill({ text }: { text: string }) {
  return (
    <button className="text-[12px] font-medium text-gray-500 bg-accent/30 border border-border/50 px-3 py-1 rounded-md hover:bg-accent hover:text-gray-300 transition-colors">
      {text}
    </button>
  )
}
