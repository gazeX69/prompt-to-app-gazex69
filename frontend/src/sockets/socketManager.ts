import { socketService } from '../services/socket'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'
import { usePreviewStore } from '../stores/preview.store'
import { normalizeExecutionState } from '../runtime/executionContract'

function onTerminalLine(data: { id: string; text: string; type: 'stdout' | 'stderr' | 'info' }) {
  if (data.text) useTerminalStore.getState().addLine({ text: data.text, type: data.type })
}

function onAgentState(state: string) {
  useAgentStore.getState().setState(normalizeExecutionState(state))
}

function onAgentActivity(data: { message: string; project_id: string }) {
  useAgentStore.getState().addActivity(data.message)
}

function onPreviewReady(data: { project_id: string; url: string; run_id?: string; workspace?: string }) {
  usePreviewStore.getState().setUrl(data.url, data.run_id)
  useAgentStore.getState().setState('PREVIEW_READY')
  useAgentStore.getState().addActivity(`Preview mounted at ${data.url} (run: ${data.run_id || 'unknown'})`)
}

function onRuntimeError(data: { code: string; category: string; message: string; source?: string }) {
  useTerminalStore.getState().addLine({
    text: `[${data.code}] ${data.message}`,
    type: 'stderr',
  })
  useAgentStore.getState().addActivity(`${data.code}: ${data.category}`)
}

function onExecutionEvent(data: { type: string; state?: string; code?: string; message?: string }) {
  if (data.type === 'state_transition' && data.state) {
    useAgentStore.getState().setState(normalizeExecutionState(data.state))
  }
}

const APP_EVENTS = [
  ['terminal_line', onTerminalLine],
  ['agent_state', onAgentState],
  ['agent_activity', onAgentActivity],
  ['preview_ready', onPreviewReady],
  ['runtime_error', onRuntimeError],
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
