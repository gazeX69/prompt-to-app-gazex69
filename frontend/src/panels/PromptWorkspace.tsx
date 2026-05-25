import { useState, useRef, useEffect } from 'react'
import { Send, Wrench, AlignLeft, WifiOff } from 'lucide-react'
import { useAgentStore } from '../stores/agent.store'
import type { AgentState } from '../stores/agent.store'
import { useSkillsStore } from '../stores/skills.store'
import { useTerminalStore } from "../stores/terminal.store"
import { usePreviewStore } from "../stores/preview.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { api } from "../services/api"
import { runBrainPreflight, type BrainDecisionResult } from "../api/workspace.api"
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

type PreflightStatus = "idle" | "loading" | "needs_confirmation" | "error"

function requiresPreflightConfirmation(result: BrainDecisionResult): boolean {
  if (result.decision === "ask_user_before_generate") return true
  if (result.decision === "provider_required") return true
  if (result.decision === "provider_review_only") return true
  return result.decision === "compose_cases" && result.scope_analysis.is_broad
}

function buildRecommendedMvpPrompt(originalPrompt: string, result: BrainDecisionResult): string {
  const features = result.recommended_mvp.features.map(feature => `- ${feature}`).join("\n")
  return `Original request:
${originalPrompt}

Use this confirmed MVP scope:
Title: ${result.recommended_mvp.title}

Features:
${features}

Constraints:
- Build the smallest working MVP.
- Use simple local/mock data unless backend/database/auth is explicitly required.
- Avoid adding unrequested external services.`
}

export default function PromptWorkspace() {
  const [prompt, setPrompt] = useState('')
  const [autoRepair, setAutoRepair] = useState(true)
  const [preflightStatus, setPreflightStatus] = useState<PreflightStatus>("idle")
  const [preflightResult, setPreflightResult] = useState<BrainDecisionResult | null>(null)
  const [preflightError, setPreflightError] = useState<string | null>(null)
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
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
  const preflightRequestRef = useRef(0)
  const preflightLoadingRef = useRef(false)
  const generationStartingRef = useRef(false)

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

  const startGeneration = async (generationPrompt: string) => {
    const finalPrompt = generationPrompt.trim()
    if (!finalPrompt) return
    if (!canGenerate(effectiveState)) return
    if (generationStartingRef.current) return
    
    useTerminalStore.getState().clear()
    useTerminalStore.getState().addLine({ text: `[Client] Sending generation request...`, type: 'info' })
    setStartTime(Date.now())
    setAgentState('GENERATING')
    useAgentStore.setState({ activities: [] })
    generationStartingRef.current = true
    
    const enabledNames = skills.filter(s => enabled[s.name] !== false).map(s => s.name)
    
    try {
      await api.post("/generate", {
        prompt: finalPrompt,
        project_id: activeWorkspaceId || `proj-${Date.now()}`,
        auto_repair: autoRepair,
        max_repair_attempts: 3,
        enabled_skills: enabledNames.length > 0 ? enabledNames : undefined
      })
    } catch (err) {
      console.error('Failed to start generation:', err)
      useTerminalStore.getState().addLine({ text: `[Client] HTTP error: ${err}`, type: 'stderr' })
      setAgentState('FAILED')
    } finally {
      generationStartingRef.current = false
    }
  }

  const resetPreflight = () => {
    preflightLoadingRef.current = false
    setPreflightStatus("idle")
    setPreflightResult(null)
    setPreflightError(null)
    setPendingPrompt(null)
  }

  const invalidatePreflight = () => {
    preflightRequestRef.current += 1
    resetPreflight()
  }

  const handleGenerate = async () => {
    const submittedPrompt = prompt.trim()
    if (!submittedPrompt) return
    if (!canGenerate(effectiveState)) return
    if (preflightLoadingRef.current || preflightStatus === "loading") return

    const requestId = preflightRequestRef.current + 1
    preflightRequestRef.current = requestId
    preflightLoadingRef.current = true
    setPendingPrompt(submittedPrompt)
    setPreflightResult(null)
    setPreflightError(null)
    setPreflightStatus("loading")

    try {
      const result = await runBrainPreflight(submittedPrompt)
      if (preflightRequestRef.current !== requestId) return
      preflightLoadingRef.current = false
      if (requiresPreflightConfirmation(result)) {
        setPreflightResult(result)
        setPreflightStatus("needs_confirmation")
        useTerminalStore.getState().addLine({ text: `[Preflight] Scope confirmation required: ${result.reason}`, type: 'info' })
        return
      }

      resetPreflight()
      await startGeneration(submittedPrompt)
    } catch (err) {
      if (preflightRequestRef.current !== requestId) return
      preflightLoadingRef.current = false
      console.error('Failed to analyze prompt scope:', err)
      setPreflightError(err instanceof Error ? err.message : "Preflight failed.")
      setPreflightStatus("error")
    }
  }

  const handleUseRecommendedMvp = async () => {
    if (!pendingPrompt || !preflightResult) return
    const narrowedPrompt = buildRecommendedMvpPrompt(pendingPrompt, preflightResult)
    resetPreflight()
    await startGeneration(narrowedPrompt)
  }

  const handleGenerateAnyway = async () => {
    if (!pendingPrompt) return
    const originalPrompt = pendingPrompt
    resetPreflight()
    await startGeneration(originalPrompt)
  }

  const handleCancelPreflight = () => {
    resetPreflight()
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
              disabled={!canGenerate(effectiveState) || preflightStatus === "loading"}
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

        {preflightStatus === "loading" && (
          <div className="mb-3 rounded-lg border border-blue-400/20 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
            Analyzing prompt scope...
          </div>
        )}

        {preflightStatus === "needs_confirmation" && preflightResult && (
          <div className="mb-3 rounded-lg border border-yellow-400/25 bg-yellow-500/10 p-4 text-left">
            <div className="text-sm font-semibold text-yellow-100">This prompt is broad and needs scope confirmation.</div>
            <p className="mt-1 text-[13px] text-yellow-100/80">{preflightResult.reason}</p>

            <div className="mt-3 grid gap-2 text-[12px] text-gray-300 sm:grid-cols-3">
              <div><span className="text-gray-500">Domain:</span> {preflightResult.signature.domain}</div>
              <div><span className="text-gray-500">Complexity:</span> {preflightResult.signature.complexity}</div>
              <div><span className="text-gray-500">Risk:</span> {preflightResult.scope_analysis.risk_level}</div>
            </div>

            <div className="mt-3">
              <div className="text-[12px] font-medium text-gray-200">{preflightResult.recommended_mvp.title}</div>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[12px] text-gray-400">
                {preflightResult.recommended_mvp.features.map(feature => (
                  <li key={feature}>{feature}</li>
                ))}
              </ul>
            </div>

            {preflightResult.scope_analysis.missing_decisions.length > 0 && (
              <div className="mt-3">
                <div className="text-[12px] font-medium text-gray-200">Missing decisions</div>
                <ul className="mt-1 space-y-1 text-[12px] text-gray-400">
                  {preflightResult.scope_analysis.missing_decisions.map(decision => (
                    <li key={decision.key}>{decision.question}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleUseRecommendedMvp}
                disabled={!canGenerate(effectiveState)}
                className="rounded-md bg-gray-100 px-3 py-1.5 text-[12px] font-medium text-black transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Use Recommended MVP
              </button>
              <button
                type="button"
                onClick={handleGenerateAnyway}
                disabled={!canGenerate(effectiveState)}
                className="rounded-md border border-border px-3 py-1.5 text-[12px] font-medium text-gray-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Generate Anyway
              </button>
              <button
                type="button"
                onClick={handleCancelPreflight}
                className="rounded-md border border-transparent px-3 py-1.5 text-[12px] font-medium text-gray-400 transition hover:bg-white/5"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {preflightStatus === "error" && (
          <div className="mb-3 rounded-lg border border-red-400/25 bg-red-500/10 p-4 text-left">
            <div className="text-sm font-semibold text-red-100">Could not analyze prompt scope. You can try again or generate anyway.</div>
            {preflightError && <p className="mt-1 text-[12px] text-red-100/75">{preflightError}</p>}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={!canGenerate(effectiveState)}
                className="rounded-md border border-border px-3 py-1.5 text-[12px] font-medium text-gray-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Try Again
              </button>
              <button
                type="button"
                onClick={handleGenerateAnyway}
                disabled={!canGenerate(effectiveState)}
                className="rounded-md bg-gray-100 px-3 py-1.5 text-[12px] font-medium text-black transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Generate Anyway
              </button>
              <button
                type="button"
                onClick={handleCancelPreflight}
                className="rounded-md border border-transparent px-3 py-1.5 text-[12px] font-medium text-gray-400 transition hover:bg-white/5"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-panel rounded-xl border border-border shadow-sm flex flex-col focus-within:border-gray-500 transition-colors overflow-hidden shrink-0">
          <textarea
            className="w-full bg-transparent border-none px-4 py-4 text-[14px] text-gray-200 placeholder:text-gray-500 focus:outline-none resize-none leading-relaxed"
            rows={4}
            placeholder="Describe what you want to build..."
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value)
              if (preflightStatus !== "idle") {
                invalidatePreflight()
              }
            }}
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
              disabled={!prompt.trim() || !canGenerate(effectiveState) || preflightStatus === "loading"}
              className="bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-white text-black font-medium text-[12px] px-4 py-1.5 rounded-md flex items-center transition-colors"
            >
              <Send className="w-3.5 h-3.5 mr-2" />
              {preflightStatus === "loading" ? "Analyzing" : "Generate"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
