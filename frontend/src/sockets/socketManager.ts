import { socketService } from '../services/socket'
import { useAgentStore } from '../stores/agent.store'
import type { AgentState } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'
import { usePreviewStore } from '../stores/preview.store'

function onTerminalLine(data: { id: string; text: string; type: 'stdout' | 'stderr' | 'info' }) {
  if (data.text) useTerminalStore.getState().addLine({ text: data.text, type: data.type })
}

function onAgentState(state: AgentState) {
  useAgentStore.getState().setState(state)
}

function onAgentActivity(data: { message: string; project_id: string }) {
  useAgentStore.getState().addActivity(data.message)
}

function onPreviewReady(data: { project_id: string; url: string }) {
  usePreviewStore.getState().setUrl(data.url)
  useAgentStore.getState().addActivity(`Preview mounted at ${data.url}`)
}

export function initSocket() {
  const socket = socketService.connect()
  socket.off('terminal_line', onTerminalLine)
  socket.off('agent_state', onAgentState)
  socket.off('agent_activity', onAgentActivity)
  socket.off('preview_ready', onPreviewReady)
  socket.on('terminal_line', onTerminalLine)
  socket.on('agent_state', onAgentState)
  socket.on('agent_activity', onAgentActivity)
  socket.on('preview_ready', onPreviewReady)
  return socket
}

export function cleanupSocket() {
  const socket = socketService.get()
  socket.off('terminal_line', onTerminalLine)
  socket.off('agent_state', onAgentState)
  socket.off('agent_activity', onAgentActivity)
  socket.off('preview_ready', onPreviewReady)
  socketService.disconnect()
}
