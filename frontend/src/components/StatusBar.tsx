import { useAgentStore } from '../stores/agent.store'
import { Activity, CheckCircle2, XCircle, Wrench, Loader2, WifiOff } from 'lucide-react'

export default function StatusBar() {
  const state = useAgentStore(state => state.state)
  const socketConnected = useAgentStore(state => state.socketConnected)

  const renderStatus = () => {
    switch(state) {
      case 'IDLE':
        return <><Activity className="w-3.5 h-3.5 text-gray-500 mr-2" /> <span className="text-gray-400">Ready</span></>
      case 'PLANNING':
      case 'SCANNING':
      case 'SCAFFOLDING':
      case 'GENERATING':
      case 'WRITING':
      case 'VALIDATING':
      case 'INSTALLING':
      case 'BUILDING':
      case 'VERIFYING':
        return <><Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin mr-2" /> <span className="text-blue-400 capitalize">{state}...</span></>
      case 'REPAIRING':
        return <><Wrench className="w-3.5 h-3.5 text-orange-400 animate-pulse mr-2" /> <span className="text-orange-400">Repairing...</span></>
      case 'STARTING_PREVIEW':
        return <><Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin mr-2" /> <span className="text-blue-400">Starting preview...</span></>
      case 'PREVIEW_READY':
        return <><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mr-2" /> <span className="text-emerald-400">Preview Ready</span></>
      case 'COMPLETED':
        return <><CheckCircle2 className="w-3.5 h-3.5 text-green-400 mr-2" /> <span className="text-green-400">Success</span></>
      case 'FAILED':
        return <><XCircle className="w-3.5 h-3.5 text-red-400 mr-2" /> <span className="text-red-400">Failed</span></>
      case 'DISCONNECTED':
      case 'RECONNECTING':
        return <><WifiOff className="w-3.5 h-3.5 text-yellow-500 mr-2" /> <span className="text-yellow-400 capitalize">{state}</span></>
    }
  }

  return (
    <div className="h-7 bg-panel border-t border-border flex items-center px-4 text-[11px] select-none shrink-0 z-20">
      <div className="flex items-center font-medium">
        {renderStatus()}
      </div>
      <div className="ml-auto text-gray-500 flex items-center space-x-4">
        <span className={`flex items-center`}>
          <span className={`w-1.5 h-1.5 rounded-full mr-2 ${socketConnected ? 'bg-green-500' : 'bg-yellow-500'}`} />
          {socketConnected ? 'WS Connected' : 'WS Disconnected'}
        </span>
        <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-blue-500 mr-2" /> Agent</span>
      </div>
    </div>
  )
}
