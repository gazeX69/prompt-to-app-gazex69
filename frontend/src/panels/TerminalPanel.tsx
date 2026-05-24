import { Terminal as TerminalIcon, CircleDashed, WifiOff, Wifi } from 'lucide-react'
import { useTerminalStore } from '../stores/terminal.store'
import { useEffect, useRef } from 'react'
import { useAgentStore } from '../stores/agent.store'

export default function TerminalPanel() {
  const lines = useTerminalStore(state => state.lines)
  const agentState = useAgentStore(state => state.state)
  const socketConnected = useAgentStore(state => state.socketConnected)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const isWorking = ['PLANNING', 'SCANNING', 'SCAFFOLDING', 'GENERATING', 'WRITING', 'VALIDATING', 'INSTALLING', 'BUILDING', 'VERIFYING', 'REPAIRING', 'STARTING_PREVIEW'].includes(agentState)

  return (
    <div className="flex flex-col h-full bg-panel font-mono text-[12px] min-h-0">
      <div className="h-9 border-b border-border flex items-center justify-between px-4 shrink-0 bg-background/50">
        <div className="flex items-center text-gray-500 text-[11px] font-medium uppercase tracking-wider">
          <TerminalIcon className="w-3.5 h-3.5 mr-2" />
          Execution Log
        </div>
        <div className="flex items-center space-x-3">
          {!socketConnected && (
            <div className="flex items-center text-yellow-500 text-[11px] font-medium uppercase tracking-wider">
              <WifiOff className="w-3 h-3 mr-1.5" />
              Offline
            </div>
          )}
          {socketConnected && !isWorking && (
            <div className="flex items-center text-green-500 text-[11px] font-medium uppercase tracking-wider">
              <Wifi className="w-3 h-3 mr-1.5" />
              Connected
            </div>
          )}
          {isWorking && (
            <div className="flex items-center text-blue-400 text-[11px] font-medium uppercase tracking-wider">
              <CircleDashed className="w-3 h-3 mr-1.5 animate-spin" />
              Running
            </div>
          )}
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-3 space-y-1 text-[12px] leading-relaxed">
        {lines.length === 0 && !isWorking && (
          <div className="text-gray-600">Waiting for command...</div>
        )}
        {lines.length === 0 && isWorking && (
          <div className="text-yellow-600 animate-pulse">Awaiting backend output...</div>
        )}
        
        {lines.map((line) => (
          <div key={line.id} className={`flex items-start ${
            line.type === 'stderr' ? 'text-red-400' :
            line.type === 'info' ? 'text-blue-400 font-medium' : 'text-gray-300'
          }`}>
            <span className="opacity-40 mr-3 select-none shrink-0">{'>'}</span>
            <span className="break-words whitespace-pre-wrap">{line.text}</span>
          </div>
        ))}
        {isWorking && (
          <div className="flex items-center text-gray-500 mt-1">
            <span className="opacity-40 mr-3 select-none">{'>'}</span>
            <span className="animate-pulse inline-block w-1.5 h-3.5 bg-gray-500" />
          </div>
        )}
        <div ref={bottomRef} className="h-1" />
      </div>
    </div>
  )
}
