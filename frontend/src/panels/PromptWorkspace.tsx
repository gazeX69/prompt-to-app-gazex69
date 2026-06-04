import { useState, useRef, useEffect } from 'react'
import { Send, Wrench, AlignLeft, WifiOff, Layers } from 'lucide-react'


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
  if (result.decision === "local_plus_question") return true
  if (result.scope_analysis?.missing_decisions?.length > 0) return true
  return result.decision === "compose_cases" && result.scope_analysis?.is_broad
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
  const [resolvedDecisions, setResolvedDecisions] = useState<Record<string, string>>({})
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
    setResolvedDecisions({})
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
      const result = await runBrainPreflight(submittedPrompt, activeWorkspaceId)
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
    let narrowedPrompt = buildRecommendedMvpPrompt(pendingPrompt, preflightResult)
    
    if (Object.keys(resolvedDecisions).length > 0) {
      narrowedPrompt += "\n\nResolved Design Decisions:\n" + 
        Object.entries(resolvedDecisions)
          .map(([key, val]) => `- ${key}: ${val}`)
          .join("\n");
    }

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
    
    let enrichedPrompt = originalPrompt
    if (Object.keys(resolvedDecisions).length > 0) {
      enrichedPrompt += "\n\nResolved Design Decisions:\n" + 
        Object.entries(resolvedDecisions)
          .map(([key, val]) => `- ${key}: ${val}`)
          .join("\n");
    }

    await startGeneration(
      enrichedPrompt,
      result
        ? {
            originalPrompt,
            finalPrompt: enrichedPrompt,
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
          <div className="mb-5 flex min-h-0 flex-col rounded-xl border border-yellow-500/25 bg-[#0e0e12] p-5 text-left shadow-[0_12px_32px_rgba(0,0,0,0.35)] space-y-4">
            <div className="flex items-center gap-2.5 pb-3 border-b border-yellow-500/10 shrink-0">
              <span className="h-2.5 w-2.5 rounded-full bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.5)]" />
              <div className="text-xs font-bold text-yellow-500 uppercase tracking-[0.18em]">Scope Preflight & Advisory</div>
            </div>
            
            <div className="shrink-0">
              <div className="text-sm font-bold text-gray-200">Advisory: Planning required before generation</div>
              <p className="mt-1.5 text-xs text-gray-400 leading-relaxed font-sans">{preflightResult.reason}</p>
            </div>

            {preflightResult.scope_analysis.missing_decisions.length > 0 && (
              <div className="mt-2 space-y-4 border-t border-white/[0.04] pt-4 shrink-0">
                <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">
                  Design Decisions Required ({Object.keys(resolvedDecisions).length}/{preflightResult.scope_analysis.missing_decisions.length})
                </div>
                <div className="space-y-3">
                  {preflightResult.scope_analysis.missing_decisions.map((decision) => {
                    const selectedOpt = resolvedDecisions[decision.key] || "";
                    return (
                      <div key={decision.key} className="border border-white/[0.04] rounded-xl p-4 bg-[#14141A] shadow-sm space-y-3">
                        <div className="text-xs font-semibold text-gray-200">{decision.question}</div>
                        <div className="flex flex-wrap gap-2">
                          {decision.options?.map((opt: any) => (
                            <button
                              key={opt.text}
                              type="button"
                              onClick={() => setResolvedDecisions(prev => ({ ...prev, [decision.key]: opt.text }))}
                              className={`text-[10px] px-3 py-1.5 rounded-lg transition-all duration-150 border font-semibold ${
                                selectedOpt === opt.text
                                  ? "bg-blue-500/10 text-blue-300 border-blue-500/30 shadow-[0_0_12px_rgba(59,130,246,0.1)]"
                                  : "bg-[#09090C] border-white/[0.06] hover:bg-[#1a1a22] text-gray-400 hover:text-gray-200"
                              }`}
                            >
                              {opt.text}
                            </button>
                          ))}
                        </div>
                        <div>
                          <input
                            type="text"
                            placeholder="Or enter custom decision details..."
                            value={selectedOpt && !decision.options?.some((o: any) => o.text === selectedOpt) ? selectedOpt : ""}
                            onChange={(e) => setResolvedDecisions(prev => ({ ...prev, [decision.key]: e.target.value }))}
                            className="w-full bg-[#09090C] border border-white/[0.06] rounded-lg px-3 py-1.5 text-xs text-gray-300 placeholder:text-gray-600 focus:outline-none focus:border-blue-500/40 transition-colors"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="mt-2 flex shrink-0 flex-wrap gap-2 border-t border-white/[0.04] pt-4">
              <button
                type="button"
                onClick={handleUseRecommendedMvp}
                disabled={!canStartGeneration}
                className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-blue-500 active:scale-95 duration-150 disabled:cursor-not-allowed disabled:opacity-50 shadow-[0_4px_12px_rgba(59,130,246,0.25)]"
              >
                Use Recommended MVP
              </button>
              {rawGenerationBlocked ? (
                <button
                  type="button"
                  disabled
                  title="Raw generation is disabled for high-risk prompts."
                  className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2 text-xs font-bold text-gray-600 cursor-not-allowed opacity-40"
                >
                  Generate Anyway
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleGenerateAnyway}
                  disabled={!canStartGeneration}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-4 py-2 text-xs font-bold text-gray-300 hover:text-white transition hover:bg-white/[0.06] active:scale-95 duration-150 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Generate Anyway
                </button>
              )}
              <button
                type="button"
                onClick={handleCancelPreflight}
                className="rounded-lg border border-transparent px-4 py-2 text-xs font-semibold text-gray-400 hover:text-gray-200 transition hover:bg-white/[0.02]"
              >
                Cancel
              </button>
            </div>

            {rawGenerationBlocked && (
              <p className="mt-2 text-xs text-yellow-500/80 leading-relaxed font-sans">
                ⚠️ Raw generation is disabled for high-risk prompts. Use the recommended MVP or cancel and refine the prompt.
              </p>
            )}

            <div className="mt-2 grid gap-3 text-xs text-gray-400 sm:grid-cols-3 bg-[#09090C] p-3 rounded-lg border border-white/[0.03]">
              <div><span className="text-gray-500 font-semibold uppercase tracking-wider text-[9px]">Domain:</span> <span className="font-mono text-gray-300">{preflightResult.signature.domain}</span></div>
              <div><span className="text-gray-500 font-semibold uppercase tracking-wider text-[9px]">Complexity:</span> <span className="font-mono text-gray-300">{preflightResult.signature.complexity}</span></div>
              <div><span className="text-gray-500 font-semibold uppercase tracking-wider text-[9px]">Risk Level:</span> <span className="font-mono font-bold text-yellow-500 capitalize">{preflightResult.scope_analysis.risk_level}</span></div>
            </div>

            <div className="mt-2 rounded-xl border border-white/[0.04] bg-[#14141A] p-4 space-y-2">
              <div className="text-xs font-bold text-gray-200 tracking-wide">{preflightResult.recommended_mvp.title}</div>
              <div className="text-xs text-gray-400 leading-relaxed font-sans">{mvpFeatureSummary}</div>
              <div className="text-[10px] uppercase font-bold tracking-wider text-gray-500">
                {missingDecisionCount > 0 ? `⚠️ ${missingDecisionCount} unresolved decisions` : "✓ All decisions resolved"}
              </div>
            </div>

            {(implementationPlan.length > 0 || taskList.length > 0) && (
              <div className="mt-2 grid gap-4 md:grid-cols-2">
                {implementationPlan.length > 0 && (
                  <div className="rounded-xl border border-white/[0.04] bg-[#14141A] p-4 space-y-2">
                    <div className="text-xs font-bold text-gray-200 tracking-wide">Implementation Plan</div>
                    <ol className="list-decimal space-y-1 pl-4 text-xs text-gray-400 leading-relaxed font-sans">
                      {implementationPlan.slice(0, 5).map(step => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {taskList.length > 0 && (
                  <div className="rounded-xl border border-white/[0.04] bg-[#14141A] p-4 space-y-2">
                    <div className="text-xs font-bold text-gray-200 tracking-wide">Task Checklist</div>
                    <ul className="list-disc space-y-1 pl-4 text-xs text-gray-400 leading-relaxed font-sans">
                      {taskList.slice(0, 5).map(task => (
                        <li key={task}>{task}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {preflightResult.matched_cases && preflightResult.matched_cases.length > 0 && (
              <div className="mt-4 border border-white/[0.04] bg-[#0E0E12] rounded-xl p-4 shadow-sm space-y-3">
                <div className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-500 animate-pulse" />
                  Similar Past Projects Found (CBR Insights)
                </div>
                <div className="space-y-3">
                  {preflightResult.matched_cases.map((c: any) => (
                    <div key={c.id} className="border border-white/[0.04] rounded-xl p-4 bg-[#14141A] space-y-3">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-bold text-gray-200 tracking-wide">{c.title}</span>
                        <span className="text-[10px] bg-blue-500/10 border border-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full font-bold font-mono">
                          {Math.round(c.score * 100)}% Match
                        </span>
                      </div>
                      {c.summary && <p className="text-[11px] text-gray-400 leading-relaxed font-sans">{c.summary}</p>}
                      
                      {/* Similarity Scores Breakdown */}
                      {(c.structural_score !== undefined || c.cosine_score !== undefined) && (
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[9px] font-mono text-gray-500 border-t border-white/[0.04] pt-2">
                          {c.structural_score !== undefined && (
                            <span>Structural Jaccard: <span className="text-gray-400 font-semibold">{Math.round(c.structural_score * 100)}%</span></span>
                          )}
                          {c.cosine_score !== undefined && (
                            <span>Semantic Cosine: <span className="text-gray-400 font-semibold">{Math.round(c.cosine_score * 100)}%</span></span>
                          )}
                        </div>
                      )}

                      {/* Extended CBR Insights */}
                      {(c.constraints || c.solution || c.lessons_learned) && (
                        <div className="mt-3 text-xs space-y-2 bg-[#09090C] p-3 rounded-lg border border-white/[0.03]">
                          {c.constraints && c.constraints !== "None specified" && (
                            <div className="leading-relaxed font-sans">
                              <span className="text-blue-400 font-semibold">Constraints:</span> <span className="text-gray-300">{c.constraints}</span>
                            </div>
                          )}
                          {c.solution && c.solution !== "Generated components codebase" && (
                            <div className="leading-relaxed font-sans">
                              <span className="text-purple-400 font-semibold">Solution:</span> <span className="text-gray-300">{c.solution}</span>
                            </div>
                          )}
                          {c.lessons_learned && c.lessons_learned !== "None recorded" && (
                            <div className="border-t border-white/[0.04] pt-2 mt-2 text-green-400 italic font-sans flex items-start gap-1.5 leading-relaxed">
                              <span>💡</span>
                              <span>Advice: <span className="text-gray-300 not-italic">{c.lessons_learned}</span></span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {preflightResult.subdomains && preflightResult.subdomains.length > 0 && (
              <div className="mt-4 border border-white/[0.04] bg-[#0E0E12] rounded-xl p-4 shadow-sm space-y-3">
                <div className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-2">
                  <AlignLeft className="w-4 h-4 text-blue-500 animate-pulse" />
                  Domain-Driven Design (DDD) Analysis
                </div>
                <div className="space-y-3">
                  {preflightResult.subdomains.map((sub: any) => (
                    <div key={sub.name} className="border border-white/[0.04] rounded-xl p-4 bg-[#14141A] space-y-2.5 text-xs">
                      <div className="font-bold text-gray-200 tracking-wide">{sub.name}</div>
                      <p className="text-gray-400 leading-relaxed font-sans">{sub.description}</p>
                      {sub.entities && sub.entities.length > 0 && (
                        <div className="mt-3 space-y-2 bg-[#09090C] p-3 rounded-lg border border-white/[0.03]">
                          <span className="text-[10px] uppercase text-gray-500 font-bold tracking-wider">Core Entities:</span>
                          <div className="space-y-1 mt-1">
                            {sub.entities.map((ent: any) => (
                              <div key={ent.name} className="text-[11px] font-mono text-gray-300 leading-relaxed">
                                • <span className="text-blue-300 font-semibold">{ent.name}</span> (
                                <span className="text-gray-400">{ent.fields?.map((f: any) => `${f.name}: ${f.type}`).join(", ")}</span>
                                )
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {preflightResult.vertical_slices && preflightResult.vertical_slices.length > 0 && (
              <div className="mt-4 border border-white/[0.04] bg-[#0E0E12] rounded-xl p-4 shadow-sm space-y-3">
                <div className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-500 animate-pulse" />
                  Vertical Slice Implementation Roadmap
                </div>
                <div className="space-y-3">
                  {preflightResult.vertical_slices.map((slice: any) => (
                    <div key={slice.name} className="border border-white/[0.04] rounded-xl p-4 bg-[#14141A] space-y-2.5 text-xs">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-gray-200 tracking-wide">{slice.name}</span>
                        {slice.dependencies?.length > 0 && (
                          <span className="text-[10px] bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded font-mono">
                            Needs: {slice.dependencies.join(", ")}
                          </span>
                        )}
                      </div>
                      <p className="text-gray-400 leading-relaxed font-sans">{slice.description}</p>
                      <div className="mt-2.5 flex flex-wrap gap-1.5 pt-1">
                        {slice.target_components?.map((comp: string) => (
                          <span key={comp} className="text-[9px] font-mono bg-[#09090C] text-blue-300 px-2 py-0.5 rounded-md border border-white/[0.04] tracking-wide">
                            {comp}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
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

        <div className="bg-[#09090C] rounded-xl border border-white/[0.05] shadow-[0_12px_40px_rgba(0,0,0,0.4)] flex flex-col focus-within:border-blue-500/40 focus-within:shadow-[0_8px_32px_rgba(59,130,246,0.08)] transition-all duration-300 overflow-hidden shrink-0">
          <textarea
            className="w-full bg-transparent border-none px-5 py-4 text-[13px] text-gray-200 placeholder:text-gray-550 focus:outline-none resize-none leading-relaxed font-sans"
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
          
          <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.04] bg-white/[0.01]">
            <div className="flex items-center space-x-2">
              <label className="flex items-center cursor-pointer text-xs font-semibold text-gray-400 hover:text-gray-200 transition-colors px-2 py-1">
                <input 
                  type="checkbox" 
                  className="mr-2 rounded-md bg-[#09090C] border-white/[0.08] focus:ring-0 focus:ring-offset-0 text-blue-500"
                  checked={autoRepair}
                  onChange={(e) => setAutoRepair(e.target.checked)}
                />
                <Wrench className="w-3 h-3 mr-1.5 text-blue-400" />
                Auto-repair
              </label>
              {!socketConnected && state === 'IDLE' && (
                <span className="text-[10px] text-yellow-500 font-bold uppercase tracking-wider flex items-center bg-yellow-500/10 border border-yellow-500/20 px-2 py-0.5 rounded-full">
                  <WifiOff className="w-2.5 h-2.5 mr-1" />
                  Offline
                </span>
              )}
            </div>
            
            <button 
              onClick={handleGenerate}
              disabled={!prompt.trim() || !canStartGeneration || preflightStatus === "loading"}
              className="bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-500 text-white font-bold text-xs px-4.5 py-2 rounded-lg flex items-center transition-all active:scale-95 duration-150 shadow-[0_4px_12px_rgba(59,130,246,0.25)]"
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
