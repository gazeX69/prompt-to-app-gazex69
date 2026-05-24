import { socketService } from '../services/socket'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'
import { usePreviewStore } from '../stores/preview.store'
import { mapExecutionToRuntimeState, normalizeExecutionState, type RuntimeLifecycleEvent, type StructuredRuntimeError } from '../runtime/executionContract'

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
