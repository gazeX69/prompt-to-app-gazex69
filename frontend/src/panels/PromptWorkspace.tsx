import { useState, useRef, useEffect } from 'react'
import { Send, Wrench, AlignLeft, WifiOff } from 'lucide-react'
import { useAgentStore } from '../stores/agent.store'
import type { AgentState } from '../stores/agent.store'
import { useSkillsStore } from '../stores/skills.store'
import { useTerminalStore } from "../stores/terminal.store"
import { usePreviewStore } from "../stores/preview.store"
import { useWorkspaceStore } from "../stores/workspace.store"
import { api } from "../services/api"
import {
  runBrainPreflight,
  savePreflightHistory,
  type BrainDecisionResult,
  type PreflightHistoryAction,
} from "../api/workspace.api"
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

type PendingPreflightHistory = {
  originalPrompt: string
  finalPrompt: string
  action: PreflightHistoryAction
  preflightResult: BrainDecisionResult
}

function requiresPreflightConfirmation(result: BrainDecisionResult): boolean {
  if (result.decision === "ask_user_before_generate") return true
  if (result.decision === "provider_required") return true
  if (result.decision === "provider_review_only") return true
  return result.decision === "compose_cases" && result.scope_analysis.is_broad
}

function blocksRawGeneration(result: BrainDecisionResult | null): boolean {
  if (!result) return false
  if (result.planning_required === true) return true
  if (result.scope_analysis.risk_level === "high") return true
  if (result.decision === "provider_required") return true
  return result.signature.complexity === "high"
}

function buildRecommendedMvpPrompt(originalPrompt: string, result: BrainDecisionResult): string {
  const features = result.recommended_mvp.features.map(feature => `- ${feature}`).join("\n")
  const implementationPlan = (result.implementation_plan ?? []).map(step => `- ${step}`).join("\n")
  const taskList = (result.task_list ?? []).map(task => `- ${task}`).join("\n")
  return `Original request:
${originalPrompt}

Use this confirmed MVP scope:
Title: ${result.recommended_mvp.title}

Features:
${features}

Constraints:
- Build the smallest working MVP.
- Target ecosystem: react-vite.
- Build this as a React + Vite + TypeScript frontend app.
- Render the working UI at the root route "/".
- Use client-side state, mock data, or localStorage for MVP data.
- Keep the implementation previewable in the browser.
- Do not create server-side files for this MVP.
- Do not import packages that are not already declared in package.json.
${implementationPlan ? `\nImplementation plan:\n${implementationPlan}` : ""}
${taskList ? `\nTask list:\n${taskList}` : ""}`
}

export default function PromptWorkspace() {
  const [prompt, setPrompt] = useState('')
  const [autoRepair, setAutoRepair] = useState(true)
  const [preflightStatus, setPreflightStatus] = useState<PreflightStatus>("idle")
  const [preflightResult, setPreflightResult] = useState<BrainDecisionResult | null>(null)
  const [preflightError, setPreflightError] = useState<string | null>(null)
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null)
  const [showPreflightDetails, setShowPreflightDetails] = useState(false)
  const { state, setState: setAgentState, setStartTime, socketConnected } = useAgentStore()
  const previewUrl = usePreviewStore((s) => s.url)

  const generationStatus = usePreviewStore((s) => s.generationStatus)
  const generationTerminalState = agentStateFromGenerationStatus(generationStatus?.status)
  const effectiveState = generationTerminalState || state
  const canStartGeneration = canGenerate(effectiveState)
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

  const resetPreflight = () => {
    preflightLoadingRef.current = false
    setPreflightStatus("idle")
    setPreflightResult(null)
    setPreflightError(null)
    setPendingPrompt(null)
    setShowPreflightDetails(false)
  }

  const invalidatePreflight = () => {
    preflightRequestRef.current += 1
    resetPreflight()
  }

  const saveHistoryBeforeGenerate = async (history: PendingPreflightHistory) => {
    try {
      await savePreflightHistory({
        original_prompt: history.originalPrompt,
        final_prompt: history.finalPrompt,
        action: history.action,
        decision: history.preflightResult.decision,
        signature: history.preflightResult.signature,
        recommended_mvp: history.preflightResult.recommended_mvp,
        missing_decision_keys:
          history.preflightResult.scope_analysis?.missing_decisions?.map((item) => item.key) ?? [],
        workspace_id: activeWorkspaceId ?? null,
      })
    } catch (error) {
      console.warn("Failed to save preflight history", error)
    }
  }

  const startGeneration = async (
    generationPrompt: string,
    history?: PendingPreflightHistory,
  ) => {
    const finalPrompt = generationPrompt.trim()
    if (!finalPrompt) return
    if (!canStartGeneration) return
    if (generationStartingRef.current) return

    generationStartingRef.current = true
    resetPreflight()
    useTerminalStore.getState().clear()
    useTerminalStore.getState().addLine({ text: `[Client] Sending generation request...`, type: 'info' })
    setStartTime(Date.now())
    setAgentState('GENERATING')
    useAgentStore.setState({ activities: [] })

    if (history) {
      void saveHistoryBeforeGenerate({
        ...history,
        finalPrompt,
      })
    }
    
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

  const handleGenerate = async () => {
    const submittedPrompt = prompt.trim()
    if (!submittedPrompt) return
    if (!canStartGeneration) return
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
        setShowPreflightDetails(false)
        setPreflightStatus("needs_confirmation")
        useTerminalStore.getState().addLine({ text: `[Preflight] Scope confirmation required: ${result.reason}`, type: 'info' })
        return
      }

      await startGeneration(submittedPrompt, {
        originalPrompt: submittedPrompt,
        finalPrompt: submittedPrompt,
        action: "auto_continue",
        preflightResult: result,
      })
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
    const originalPrompt = pendingPrompt
    const result = preflightResult
    const narrowedPrompt = buildRecommendedMvpPrompt(pendingPrompt, preflightResult)
    await startGeneration(narrowedPrompt, {
      originalPrompt,
      finalPrompt: narrowedPrompt,
      action: "use_recommended_mvp",
      preflightResult: result,
    })
  }

  const handleGenerateAnyway = async () => {
    if (!pendingPrompt) return
    const originalPrompt = pendingPrompt
    const result = preflightResult
    if (blocksRawGeneration(result)) {
      useTerminalStore.getState().addLine({
        text: "[Preflight] Raw generation is disabled for high-risk prompts. Use the recommended MVP or refine the prompt.",
        type: "info",
      })
      return
    }
    await startGeneration(
      originalPrompt,
      result
        ? {
            originalPrompt,
            finalPrompt: originalPrompt,
            action: "generate_anyway",
            preflightResult: result,
          }
        : undefined,
    )
  }

  const handleCancelPreflight = () => {
    resetPreflight()
  }

  useEffect(() => {
    if (canStartGeneration || preflightStatus === "idle") return
    invalidatePreflight()
  }, [canStartGeneration, preflightStatus])

  useEffect(() => {
    if (state !== 'IDLE' && !generationTerminalState) {
      setAgentState('IDLE')
    }
  }, [activeWorkspaceId])

  const isConfirmingPreflight = preflightStatus === "needs_confirmation" && !!preflightResult && canStartGeneration
  const mvpFeatureSummary = preflightResult?.recommended_mvp.features.slice(0, 5).join(", ") || "Recommended MVP scope"
  const missingDecisionCount = preflightResult?.scope_analysis.missing_decisions.length ?? 0
  const implementationPlan = preflightResult?.implementation_plan ?? []
  const taskList = preflightResult?.task_list ?? []
  const rawGenerationBlocked = blocksRawGeneration(preflightResult)

  return (
    <div className="h-full min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 pb-10 md:p-8 md:pb-10">
      <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col">
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
              disabled={!canStartGeneration || preflightStatus === "loading"}
              onClick={handleGenerate}
              className="text-[12px] px-3 py-1.5 rounded border border-border text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-accent"
            >
              Retry / Fix
            </button>
          </div>
        </div>
        
        {!isConfirmingPreflight && (
          effectiveState === 'IDLE' || effectiveState === 'COMPLETED' || effectiveState === 'FAILED' ? (
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
            <div className="min-h-0 flex-1 pb-8">
              <ProgressView />
            </div>
          )
        )}

        {preflightStatus === "loading" && (
          <div className="mb-3 rounded-lg border border-blue-400/20 bg-blue-500/10 px-4 py-3 text-sm text-blue-100">
            Analyzing prompt scope...
          </div>
        )}

        {isConfirmingPreflight && preflightResult && (
          <div className="mb-3 flex min-h-0 flex-col rounded-lg border border-yellow-400/25 bg-yellow-500/10 p-4 text-left">
            <div className="shrink-0">
              <div className="text-sm font-semibold text-yellow-100">Planning required before generation</div>
              <p className="mt-1 text-[13px] text-yellow-100/80">{preflightResult.reason}</p>
            </div>

            <div className="mt-3 flex shrink-0 flex-wrap gap-2">
              <button
                type="button"
                onClick={handleUseRecommendedMvp}
                disabled={!canStartGeneration}
                className="rounded-md bg-gray-100 px-3 py-1.5 text-[12px] font-medium text-black transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Use Recommended MVP
              </button>
              {rawGenerationBlocked ? (
                <button
                  type="button"
                  disabled
                  title="Raw generation is disabled for high-risk prompts."
                  className="rounded-md border border-border px-3 py-1.5 text-[12px] font-medium text-gray-500 opacity-60 cursor-not-allowed"
                >
                  Generate Anyway
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleGenerateAnyway}
                  disabled={!canStartGeneration}
                  className="rounded-md border border-border px-3 py-1.5 text-[12px] font-medium text-gray-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Generate Anyway
                </button>
              )}
              <button
                type="button"
                onClick={handleCancelPreflight}
                className="rounded-md border border-transparent px-3 py-1.5 text-[12px] font-medium text-gray-400 transition hover:bg-white/5"
              >
                Cancel
              </button>
            </div>

            {rawGenerationBlocked && (
              <p className="mt-2 text-[12px] text-yellow-100/75">
                Raw generation is disabled for high-risk prompts. Use the recommended MVP or cancel and refine the prompt.
              </p>
            )}

            <div className="mt-3 grid gap-2 text-[12px] text-gray-300 sm:grid-cols-3">
              <div><span className="text-gray-500">Domain:</span> {preflightResult.signature.domain}</div>
              <div><span className="text-gray-500">Complexity:</span> {preflightResult.signature.complexity}</div>
              <div><span className="text-gray-500">Risk:</span> {preflightResult.scope_analysis.risk_level}</div>
            </div>

            <div className="mt-3 rounded-md border border-yellow-400/15 bg-black/10 p-3">
              <div className="text-[12px] font-medium text-gray-200">{preflightResult.recommended_mvp.title}</div>
              <div className="mt-1 text-[12px] text-gray-400">{mvpFeatureSummary}</div>
              <div className="mt-2 text-[12px] text-gray-400">
                {missingDecisionCount > 0 ? `${missingDecisionCount} unresolved decisions` : "No unresolved decisions"}
              </div>
            </div>

            {(implementationPlan.length > 0 || taskList.length > 0) && (
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {implementationPlan.length > 0 && (
                  <div className="rounded-md border border-yellow-400/15 bg-black/10 p-3">
                    <div className="text-[12px] font-medium text-gray-200">Implementation plan</div>
                    <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-[12px] text-gray-400">
                      {implementationPlan.slice(0, 5).map(step => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {taskList.length > 0 && (
                  <div className="rounded-md border border-yellow-400/15 bg-black/10 p-3">
                    <div className="text-[12px] font-medium text-gray-200">Task list</div>
                    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[12px] text-gray-400">
                      {taskList.slice(0, 5).map(task => (
                        <li key={task}>{task}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <button
              type="button"
              onClick={() => setShowPreflightDetails((value) => !value)}
              className="mt-3 w-fit text-[12px] font-medium text-yellow-100/80 transition hover:text-yellow-100"
            >
              {showPreflightDetails ? "Hide details" : "Show details"}
            </button>

            {showPreflightDetails && (
              <div className="mt-2 max-h-40 min-h-0 overflow-y-auto rounded-md border border-yellow-400/15 bg-black/10 p-3">
                <div className="text-[12px] font-medium text-gray-200">Recommended MVP features</div>
                <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[12px] text-gray-400">
                  {preflightResult.recommended_mvp.features.map(feature => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>

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
              </div>
              )}
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
                disabled={!canStartGeneration}
                className="rounded-md border border-border px-3 py-1.5 text-[12px] font-medium text-gray-200 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Try Again
              </button>
              <button
                type="button"
                onClick={handleGenerateAnyway}
                disabled={!canStartGeneration}
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
              disabled={!prompt.trim() || !canStartGeneration || preflightStatus === "loading"}
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
