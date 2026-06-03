import { socketService } from '../services/socket'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'
import { usePreviewStore } from '../stores/preview.store'
import { useWorkspaceStore } from '../stores/workspace.store'
import { mapExecutionToRuntimeState, normalizeExecutionState, type RuntimeLifecycleEvent, type StructuredRuntimeError } from '../runtime/executionContract'
import { shouldAdoptRuntimeForActiveRun } from '../stateConsistency'

function onTerminalLine(data: { id: string; text: string; type: 'stdout' | 'stderr' | 'info' }) {
  if (data.text) useTerminalStore.getState().addLine({ text: data.text, type: data.type })
}

function onAgentState(state: string) {
  const normalizedState = normalizeExecutionState(state)
  useAgentStore.getState().setState(normalizedState)
  const runtimeState = mapExecutionToRuntimeState(normalizedState)
  if (runtimeState) useAgentStore.getState().setRuntimeState(runtimeState)
  if (normalizedState === 'STARTING_PREVIEW' || normalizedState === 'FAILED') {
    usePreviewStore.getState().clear()
  }
  if (normalizedState === 'STARTING_PREVIEW') {
    usePreviewStore.getState().setGenerationFailure(null)
  }
}

function onAgentActivity(data: { message: string; project_id: string }) {
  useAgentStore.getState().addActivity(data.message)
}

function onPreviewReady(data: { project_id: string; url: string; run_id?: string; workspace?: string }) {
  const activeRunId = useWorkspaceStore.getState().activeRunId
  if (!shouldAdoptRuntimeForActiveRun(activeRunId, data.run_id)) {
    usePreviewStore.getState().clear()
    useAgentStore.getState().addActivity(`Ignored preview for non-active run: ${data.run_id}`)
    return
  }
  usePreviewStore.getState().setUrl(data.url, data.run_id)
  usePreviewStore.getState().setRuntimeStatus({
    project_id: data.project_id,
    run_id: data.run_id || null,
    status: 'running',
    port: parsePreviewPort(data.url),
    pid: null,
    url: data.url,
    started_at: null,
    last_healthcheck: null,
    error: null,
  })
  useAgentStore.getState().setState('PREVIEW_READY')
  useAgentStore.getState().addActivity(`Preview mounted at ${data.url} (run: ${data.run_id || 'unknown'})`)
}

function onRuntimeError(data: StructuredRuntimeError) {
  useAgentStore.getState().setRuntimeError(data)
  useTerminalStore.getState().addLine({
    text: `[${data.severity || 'error'}] ${data.code}: ${data.message}${data.suggestedAction ? ` | ${data.suggestedAction}` : ''}`,
    type: 'stderr',
  })
  useAgentStore.getState().addActivity(`${data.code}: ${data.category || 'runtime'}`)
}

function onRuntimeLifecycleEvent(data: RuntimeLifecycleEvent) {
  useAgentStore.getState().setRuntimeLifecycleEvent(data)
  const activeRunId = useWorkspaceStore.getState().activeRunId
  if (!shouldAdoptRuntimeForActiveRun(activeRunId, data.sessionId)) {
    usePreviewStore.getState().clear()
    return
  }
  usePreviewStore.getState().setRuntimeStatus({
    project_id: data.workspaceId || null,
    run_id: data.sessionId || null,
    status: lifecycleStatus(data.type),
    port: data.selectedPort ?? data.requestedPort ?? null,
    pid: data.processPid ?? null,
    url: data.selectedPort ? `http://127.0.0.1:${data.selectedPort}` : null,
    started_at: null,
    last_healthcheck: data.timestamp ?? null,
    error: data.error?.message || null,
  })
  if (
    data.type === 'runtime.spawn.started' ||
    data.type === 'runtime.stopping' ||
    data.type === 'runtime.stopped' ||
    data.type === 'runtime.spawn.failed' ||
    data.type === 'runtime.stop.failed' ||
    data.type === 'runtime.healthcheck.failed' ||
    data.type === 'runtime.crashed'
  ) {
    usePreviewStore.getState().clear()
  }
}

function onGenerationFailed(data: {
  project_id?: string | null
  run_id?: string | null
  stage?: string
  message?: string
  timestamp?: number | null
}) {
  const stage = data.stage || 'pre_runtime'
  const message = data.message || 'Generation failed before runtime launch'
  usePreviewStore.getState().clear()
  usePreviewStore.getState().setGenerationFailure({
    project_id: data.project_id || null,
    run_id: data.run_id || null,
    stage,
    message,
    timestamp: data.timestamp ?? Date.now(),
  })
  usePreviewStore.getState().setRuntimeStatus({
    project_id: data.project_id || null,
    run_id: data.run_id || null,
    status: 'failed',
    port: null,
    pid: null,
    url: null,
    started_at: null,
    last_healthcheck: data.timestamp ?? Date.now(),
    error: `${stage}: ${message}`,
  })
  useAgentStore.getState().setState('FAILED')
  useAgentStore.getState().setRuntimeState('FAILED')
  useAgentStore.getState().addActivity(`Generation failed before runtime (${stage})`)
}

function onGenerationStatus(data: {
  project_id?: string | null
  generation_id?: string | null
  run_id?: string | null
  current_run_id?: string | null
  active_run_id?: string | null
  latest_run_id?: string | null
  status?: string
  phase?: string
  message?: string
  detail?: Record<string, unknown>
  created_at?: number | null
  updated_at?: number | null
  runtime_run_id?: string | null
  runtime_url?: string | null
  runtime_port?: number | null
}) {
  usePreviewStore.getState().setGenerationStatus({
    project_id: data.project_id || null,
    generation_id: data.generation_id || null,
    run_id: data.run_id || null,
    current_run_id: data.current_run_id || null,
    active_run_id: data.active_run_id || null,
    latest_run_id: data.latest_run_id || null,
    status: data.status || 'unknown',
    phase: data.phase || 'none',
    message: data.message || '',
    detail: data.detail || {},
    created_at: data.created_at ?? null,
    updated_at: data.updated_at ?? null,
    runtime_run_id: data.runtime_run_id || null,
    runtime_url: data.runtime_url || null,
    runtime_port: data.runtime_port ?? null,
  })
}

function lifecycleStatus(type: RuntimeLifecycleEvent['type']): string {
  if (type === 'runtime.ready') return 'running'
  if (type === 'runtime.stopped') return 'stopped'
  if (type === 'runtime.spawn.failed' || type === 'runtime.stop.failed' || type === 'runtime.healthcheck.failed' || type === 'runtime.crashed') return 'failed'
  return 'starting'
}

function parsePreviewPort(url: string): number | null {
  try {
    const parsed = new URL(url)
    return parsed.port ? Number(parsed.port) : null
  } catch {
    return null
  }
}

function onExecutionEvent(data: { type: string; state?: string; code?: string; message?: string; project_id?: string | null; run_id?: string | null; stage?: string; timestamp?: number }) {
  if (data.type === 'generation_status') {
    onGenerationStatus(data)
    return
  }
  if (data.type === 'generation_failed') {
    onGenerationFailed(data)
    return
  }
  if (data.type === 'state_transition' && data.state) {
    const normalizedState = normalizeExecutionState(data.state)
    useAgentStore.getState().setState(normalizedState)
    const runtimeState = mapExecutionToRuntimeState(normalizedState)
    if (runtimeState) useAgentStore.getState().setRuntimeState(runtimeState)
  }
}

const APP_EVENTS = [
  ['terminal_line', onTerminalLine],
  ['agent_state', onAgentState],
  ['agent_activity', onAgentActivity],
  ['preview_ready', onPreviewReady],
  ['runtime_error', onRuntimeError],
  ['runtime_lifecycle_event', onRuntimeLifecycleEvent],
  ['execution_event', onExecutionEvent],
] as const

function attachAppListeners() {
  const socket = socketService.get()
  if (!socket) return
  for (const [event, handler] of APP_EVENTS) {
    socket.off(event, handler as (...args: any[]) => void)
    socket.on(event, handler as (...args: any[]) => void)
  }
  console.log(`[Socket] App listeners attached (${APP_EVENTS.length} events)`)
}

function detachAppListeners() {
  const socket = socketService.get()
  if (!socket) return
  for (const [event, handler] of APP_EVENTS) {
    socket.off(event, handler as (...args: any[]) => void)
  }
  console.log(`[Socket] App listeners detached`)
}

function attachConnectionMonitor() {
  const socket = socketService.get()
  if (!socket) return

  socket.off('connect', onConnect)
  socket.off('disconnect', onDisconnect)
  socket.off('connect_error', onConnectError)
  socket.on('connect', onConnect)
  socket.on('disconnect', onDisconnect)
  socket.on('connect_error', onConnectError)
}

function detachConnectionMonitor() {
  const socket = socketService.get()
  if (!socket) return
  socket.off('connect', onConnect)
  socket.off('disconnect', onDisconnect)
  socket.off('connect_error', onConnectError)
}

function onConnect() {
  console.log(`[Socket] Connection monitor: connected`)
  useAgentStore.getState().setSocketConnected(true)
  // Re-attach app listeners on reconnect
  attachAppListeners()
}

function onDisconnect(reason: string) {
  console.warn(`[Socket] Connection monitor: disconnected (${reason})`)
  useAgentStore.getState().setSocketConnected(false)
}

function onConnectError(error: Error) {
  console.error(`[Socket] Connection monitor: error (${error.message})`)
  useAgentStore.getState().setSocketConnected(false)
}

/**
 * Initialize socket + attach listeners.
 * Safe to call multiple times — idempotent.
 * Separates socket lifecycle (singleton, managed by SocketService)
 * from listener lifecycle (attached/detached per mount).
 */
export function initSocket() {
  socketService.connect()
  attachAppListeners()
  attachConnectionMonitor()
}

/**
 * Cleanup listeners only.
 * Does NOT disconnect the socket singleton.
 * StrictMode-safe: the socket survives remounts.
 */
export function cleanupSocket() {
  detachAppListeners()
  detachConnectionMonitor()
}
