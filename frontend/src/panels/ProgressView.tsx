import { useEffect, useState } from 'react'
import { useAgentStore } from '../stores/agent.store'
import type { AgentState } from '../stores/agent.store'
import { CheckCircle2, Circle, Loader2, XCircle, WifiOff } from 'lucide-react'

const STAGES = [
  { id: 'PLANNING', label: 'AI Planning' },
  { id: 'SCAFFOLDING', label: 'Scaffolding Template' },
  { id: 'GENERATING', label: 'Feature Generation' },
  { id: 'WRITING', label: 'Writing Files' },
  { id: 'VALIDATING', label: 'Validating Contract' },
  { id: 'INSTALLING', label: 'Installing Dependencies' },
  { id: 'BUILDING', label: 'Building Project' },
  { id: 'REPAIRING', label: 'Auto Repair (if needed)' },
  { id: 'STARTING_PREVIEW', label: 'Starting Preview' },
  { id: 'PREVIEW_READY', label: 'Preview Ready' },
  { id: 'VERIFYING', label: 'Runtime Verification' },
  { id: 'COMPLETED', label: 'Completed' }
]

function getStageIndex(state: AgentState): number {
  if (state === 'IDLE') return -1
  if (state === 'DISCONNECTED' || state === 'RECONNECTING') return -1
  if (state === 'FAILED' || state === 'COMPLETED') return STAGES.length
  return STAGES.findIndex(s => s.id === state)
}

export function ProgressView() {
  const { state, activities, startTime, socketConnected } = useAgentStore()
  const [elapsed, setElapsed] = useState(0)
  const [lastActiveStage, setLastActiveStage] = useState(-1)

  useEffect(() => {
    if (!startTime || state === 'IDLE' || state === 'COMPLETED' || state === 'FAILED') return
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)
    return () => clearInterval(interval)
  }, [startTime, state])

  useEffect(() => {
    if (state !== 'FAILED' && state !== 'COMPLETED' && state !== 'IDLE') {
       const index = STAGES.findIndex(s => s.id === state)
       if (index > lastActiveStage) setLastActiveStage(index)
    }
  }, [state, lastActiveStage])

  const currentIndex = getStageIndex(state)

  if (state === 'DISCONNECTED' || state === 'RECONNECTING') {
    return (
      <div className="w-full max-w-4xl mx-auto flex flex-col space-y-6 animate-in fade-in duration-500">
        <div className="flex flex-col items-center justify-center py-12">
          <WifiOff className="w-10 h-10 text-yellow-500 mb-4" />
          <h2 className="text-lg font-semibold text-yellow-400">Connection Interrupted</h2>
          <p className="text-[13px] text-gray-400 mt-2">
            {state === 'RECONNECTING' 
              ? 'Reconnecting to backend... Your session data is preserved.'
              : 'Waiting for backend connection...'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col space-y-6 animate-in fade-in duration-500">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-200">Orchestration Progress</h2>
          <p className="text-[13px] text-gray-500 mt-1">Executing AI generation pipeline...</p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-mono text-gray-300 font-light">
            {Math.floor(elapsed / 60).toString().padStart(2, '0')}:{(elapsed % 60).toString().padStart(2, '0')}
          </div>
          <div className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold mt-1">
            Elapsed Time
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Stages List */}
        <div className="space-y-4">
          <h3 className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold mb-2">Execution Stages</h3>
          {STAGES.map((stage, i) => {
            let status = 'pending'
            if (state === 'FAILED') {
              if (i === lastActiveStage) status = 'failed'
              else if (i < lastActiveStage) status = 'completed'
              else status = 'pending'
            } else {
              if (i < currentIndex || state === 'COMPLETED') status = 'completed'
              else if (i === currentIndex) status = 'active'
            }

            if (stage.id === 'REPAIRING' && status !== 'active' && !activities.some(a => a.message.includes('Repaired') || a.message.includes('failed'))) {
               if (status === 'completed') status = 'pending' 
            }

            return (
              <div key={stage.id} className={`flex items-center space-x-3 text-[13px] transition-opacity duration-300 ${status === 'pending' ? 'opacity-40' : 'opacity-100'}`}>
                {status === 'completed' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                {status === 'active' && <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />}
                {status === 'pending' && <Circle className="w-4 h-4 text-gray-600" />}
                {status === 'failed' && <XCircle className="w-4 h-4 text-red-500" />}
                <span className={`${status === 'active' ? 'text-gray-200 font-medium' : 'text-gray-400'}`}>
                  {stage.label}
                </span>
              </div>
            )
          })}
        </div>

        {/* Live Activity Stream */}
        <div className="flex flex-col bg-background rounded-xl border border-border overflow-hidden h-[300px]">
          <div className="px-4 py-2 border-b border-border bg-panel flex items-center justify-between">
            <span className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold">Activity Stream</span>
            {!socketConnected && <span className="text-[11px] text-yellow-400 font-medium bg-yellow-500/10 px-2 py-0.5 rounded">Disconnected</span>}
            {state === 'FAILED' && <span className="text-[11px] text-red-400 font-medium bg-red-500/10 px-2 py-0.5 rounded">Failed</span>}
            {state === 'COMPLETED' && <span className="text-[11px] text-green-400 font-medium bg-green-500/10 px-2 py-0.5 rounded">Success</span>}
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3 font-mono text-[12px]">
            {activities.length === 0 ? (
              <div className="text-gray-600 italic">Waiting for events...</div>
            ) : (
              activities.map((act) => (
                <div key={act.id} className="flex space-x-3 text-gray-300 animate-in slide-in-from-right-2 fade-in">
                  <span className="text-gray-500 shrink-0">
                    {new Date(act.timestamp).toLocaleTimeString([], { hour12: false })}
                  </span>
                  <span className={act.message.toLowerCase().includes('error') || act.message.toLowerCase().includes('failed') ? 'text-red-400' : 'text-gray-300'}>
                    {act.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
