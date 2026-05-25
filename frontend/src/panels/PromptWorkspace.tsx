import { useState, useRef, useEffect } from 'react'
import { Send, Wrench, AlignLeft, WifiOff } from 'lucide-react'
import { useAgentStore } from '../stores/agent.store'
import type { AgentState } from '../stores/agent.store'
import { useSkillsStore } from '../stores/skills.store'
import { useTerminalStore } from "../stores/terminal.store"
import { usePreviewStore } from "../stores/preview.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { api } from "../services/api"
import { ProgressView } from "./ProgressView"

function canGenerate(state: AgentState): boolean {
  return state === 'IDLE' || state === 'FAILED' || state === 'COMPLETED'
}

// const TERMINAL_GENERATION_STATUSES = new Set([
//   'succeeded',
//   'success',
//   'completed',
//   'failed',
//   'failure',
//   'runtime_failed',
//   'cancelled',
//   'canceled',
// ])

function normalizeStatus(value?: string | null) {
  return String(value || '').toLowerCase()
}

// function isTerminalGenerationStatus(value?: string | null) {
//   return TERMINAL_GENERATION_STATUSES.has(normalizeStatus(value))
// }

function agentStateFromGenerationStatus(value?: string | null): AgentState | null {
  const status = normalizeStatus(value)

  if (status === 'succeeded' || status === 'success' || status === 'completed') {
    return 'COMPLETED'
  }

  if (status === 'failed' || status === 'failure' || status === 'runtime_failed') {
    return 'FAILED'
  }

  return null
}

export default function PromptWorkspace() {
  const [prompt, setPrompt] = useState('')
  const [autoRepair, setAutoRepair] = useState(true)
  const { state, setState: setAgentState, setStartTime, socketConnected } = useAgentStore()
  const previewUrl = usePreviewStore((s) => s.url)

  const generationStatus = usePreviewStore((s) => s.generationStatus)
  const generationTerminalState = agentStateFromGenerationStatus(generationStatus?.status)
  const effectiveState = generationTerminalState || state
  // const showProgress =
  //   effectiveState !== 'IDLE' &&
  //   effectiveState !== 'FAILED' &&
  //   effectiveState !== 'COMPLETED' &&
  //   effectiveState !== 'DISCONNECTED' &&
  //   effectiveState !== 'RECONNECTING'

  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const activeWorkspace = useWorkspaceStore((s) => s.activeWorkspaceId ? s.workspaces[s.activeWorkspaceId] : null)
  const { enabled, skills } = useSkillsStore()
  const failTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const safeSetAgentState = useAgentStore((s) => s.setState)
  
  // Fail-safe: if generation takes >120s without terminal state, auto-fail
  useEffect(() => {
    if (state === 'GENERATING' || state === 'INSTALLING' || state === 'BUILDING' || state === 'REPAIRING' || state === 'STARTING_PREVIEW' || state === 'VERIFYING') {
      if (!failTimerRef.current) {
        failTimerRef.current = setTimeout(() => {
          console.warn(`[FailSafe] Generation stalled at ${state} for 120s — forcing failed`)
          safeSetAgentState('FAILED')
          useTerminalStore.getState().addLine({ text: `[FailSafe] Generation timed out after 120s at state: ${state}`, type: 'stderr' })
        }, 120000)
      }
    } else {
      if (failTimerRef.current) {
        clearTimeout(failTimerRef.current)
        failTimerRef.current = null
      }
    }
    return () => {
      if (failTimerRef.current) {
        clearTimeout(failTimerRef.current)
        failTimerRef.current = null
      }
    }
  }, [state, safeSetAgentState])

  useEffect(() => {
    if (!generationTerminalState) return

    if (state !== generationTerminalState) {
      setAgentState(generationTerminalState)
    }
  }, [generationTerminalState, state, setAgentState])

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    if (!canGenerate(effectiveState)) return
    
    useTerminalStore.getState().clear()
    useTerminalStore.getState().addLine({ text: `[Client] Sending generation request...`, type: 'info' })
    setStartTime(Date.now())
    setAgentState('GENERATING')
    useAgentStore.setState({ activities: [] })
    
    const enabledNames = skills.filter(s => enabled[s.name] !== false).map(s => s.name)
    
    try {
      await api.post("/generate", {
        prompt: prompt,
        project_id: activeWorkspaceId || `proj-${Date.now()}`,
        auto_repair: autoRepair,
        max_repair_attempts: 3,
        enabled_skills: enabledNames.length > 0 ? enabledNames : undefined
      })
    } catch (err) {
      console.error('Failed to start generation:', err)
      useTerminalStore.getState().addLine({ text: `[Client] HTTP error: ${err}`, type: 'stderr' })
      setAgentState('FAILED')
    }
  }

  useEffect(() => {
    if (state !== 'IDLE' && !generationTerminalState) {
      setAgentState('IDLE')
    }
  }, [activeWorkspaceId])

  return (
    <div className="flex-1 flex flex-col min-h-0 p-4 md:p-8 overflow-y-auto">
      <div className="max-w-4xl w-full mx-auto flex-1 flex flex-col justify-end pb-4">
        <div className="mb-4 border border-border bg-panel rounded-lg p-3 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-widest text-gray-500 font-semibold">Generate</div>
            <div className="text-sm text-gray-200 truncate">
            {previewUrl || generationTerminalState === 'COMPLETED'
              ? 'Generated app is ready to preview.'
              : effectiveState === 'IDLE'
                ? `Describe what to build in ${activeWorkspace?.name || 'this project'}.`
                : generationTerminalState === 'FAILED'
                  ? 'Generation failed. Review the activity stream or retry.'
                  : 'Generation in progress.'}
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <button
              type="button"
              disabled={!previewUrl}
              onClick={() => previewUrl && window.open(previewUrl, '_blank', 'noopener,noreferrer')}
              className="text-[12px] px-3 py-1.5 rounded border border-border text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent"
            >
              Open Preview
            </button>
            <button
              type="button"
              disabled={!canGenerate(effectiveState)}
              onClick={handleGenerate}
              className="text-[12px] px-3 py-1.5 rounded border border-border text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent"
            >
              Retry / Fix
            </button>
          </div>
        </div>
        
        {effectiveState === 'IDLE' || effectiveState === 'COMPLETED' || effectiveState === 'FAILED' ? (
          <div className="flex-1 flex flex-col justify-center items-center text-center opacity-50 mb-12 min-h-[120px]">
             <AlignLeft className="w-8 h-8 mb-4 text-gray-500" />
             <h2 className="text-lg font-medium text-gray-200">What should AI Agent build?</h2>
             <p className="text-[13px] text-gray-400 mt-2 max-w-sm">
               Describe the app, page, or change you want for this project.
             </p>
          </div>
        ) : effectiveState === 'DISCONNECTED' || effectiveState === 'RECONNECTING' ? (
          <div className="flex-1 flex flex-col justify-center items-center text-center mb-12 min-h-[120px]">
             <WifiOff className="w-8 h-8 mb-4 text-yellow-500" />
             <h2 className="text-lg font-medium text-yellow-400">Connection Lost</h2>
             <p className="text-[13px] text-gray-400 mt-2 max-w-sm">
               {effectiveState === 'RECONNECTING' 
                 ? 'Reconnecting to backend... Your session will resume.'
                 : 'Backend is offline. Waiting for connection...'}
             </p>
          </div>
        ) : (
          <div className="flex-1 mb-8 overflow-y-auto">
            <ProgressView />
          </div>
        )}

        <div className="bg-panel rounded-xl border border-border shadow-sm flex flex-col focus-within:border-gray-500 transition-colors overflow-hidden shrink-0">
          <textarea
            className="w-full bg-transparent border-none px-4 py-4 text-[14px] text-gray-200 placeholder:text-gray-500 focus:outline-none resize-none leading-relaxed"
            rows={4}
            placeholder="Describe what you want to build..."
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
              {!socketConnected && state === 'IDLE' && (
                <span className="text-[11px] text-yellow-500 font-medium flex items-center">
                  <WifiOff className="w-3 h-3 mr-1" />
                  Offline
                </span>
              )}
            </div>
            
            <button 
              onClick={handleGenerate}
              disabled={!prompt.trim() || !canGenerate(effectiveState)}
              className="bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white text-black font-medium text-[12px] px-4 py-1.5 rounded-md flex items-center transition-colors"
            >
              <Send className="w-3.5 h-3.5 mr-2" />
              Generate
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
