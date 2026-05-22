import { useAgentStore } from '../stores/agent.store'
import { Activity, CheckCircle2, XCircle, Wrench, Loader2 } from 'lucide-react'

export default function StatusBar() {
  const state = useAgentStore(state => state.state)

  const renderStatus = () => {
    switch(state) {
      case 'idle':
        return <><Activity className="w-3.5 h-3.5 text-gray-500 mr-2" /> <span className="text-gray-400">Ready</span></>
      case 'generating':
      case 'installing':
      case 'building':
        return <><Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin mr-2" /> <span className="text-blue-400 capitalize">{state}...</span></>
      case 'repairing':
        return <><Wrench className="w-3.5 h-3.5 text-orange-400 animate-pulse mr-2" /> <span className="text-orange-400">Repairing...</span></>
      case 'success':
        return <><CheckCircle2 className="w-3.5 h-3.5 text-green-400 mr-2" /> <span className="text-green-400">Success</span></>
      case 'failed':
        return <><XCircle className="w-3.5 h-3.5 text-red-400 mr-2" /> <span className="text-red-400">Failed</span></>
    }
  }

  return (
    <div className="h-7 bg-panel border-t border-border flex items-center px-4 text-[11px] select-none shrink-0 z-20">
      <div className="flex items-center font-medium">
        {renderStatus()}
      </div>
      <div className="ml-auto text-gray-500 flex items-center space-x-4">
        <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-gray-500 mr-2" /> Vite</span>
        <span className="flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-blue-500 mr-2" /> Agent</span>
      </div>
    </div>
  )
}
