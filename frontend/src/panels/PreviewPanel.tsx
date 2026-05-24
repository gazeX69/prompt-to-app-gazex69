import { useEffect, useState } from 'react'
import { RotateCw, ExternalLink, Globe, AlertTriangle, WifiOff, Loader2 } from 'lucide-react'
import { usePreviewStore } from '../stores/preview.store'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'

export default function PreviewPanel() {
  const { url, isReloading } = usePreviewStore()
  const { state, activities, runtimeState, latestRuntimeLifecycleEvent } = useAgentStore()
  const { lines } = useTerminalStore()
  
  const runId = usePreviewStore(state => state.runId) || 'legacy'
  const [iframeUrl, setIframeUrl] = useState('')

  useEffect(() => {
    if (url) {
      setIframeUrl(`${url}?run_id=${runId}&t=${Date.now()}`)
    } else {
      setIframeUrl('')
    }
  }, [url, runId])
  
  useEffect(() => {
    if (iframeUrl) {
      console.log(`[PreviewFrame] mounted / updated: ${iframeUrl}`)
    }
    return () => {
      if (iframeUrl) {
        console.log(`[PreviewFrame] destroyed: ${iframeUrl}`)
      }
    }
  }, [iframeUrl])

  const displayUrl = (() => {
    if (!url) return 'Preview offline'
    try {
      return new URL(url).host
    } catch {
      return url
    }
  })()

  const reloadPreview = () => {
    if (url) setIframeUrl(`${url}?run_id=${runId}&t=${Date.now()}`)
  }

  const openPreview = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="flex flex-col h-full bg-background min-w-0">
      {/* Browser Chrome */}
      <div className="h-14 border-b border-border bg-panel flex items-center px-4 shrink-0">
        <div className="flex space-x-1.5 mr-4 shrink-0">
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 hover:bg-red-500 transition-colors" />
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 hover:bg-yellow-500 transition-colors" />
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 hover:bg-green-500 transition-colors" />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase tracking-widest text-gray-500 font-semibold">Preview</div>
          <div className="h-7 bg-background border border-border rounded flex items-center px-3 text-[12px] text-gray-300 truncate max-w-xl">
            {displayUrl}
          </div>
        </div>
        
        <div className="flex items-center space-x-1 ml-4 shrink-0">
          <div className={`px-2 py-1 rounded border text-[10px] font-mono ${
            runtimeState === 'READY'
              ? 'border-green-500/30 text-green-400 bg-green-500/10'
              : runtimeState === 'FAILED'
                ? 'border-red-500/30 text-red-400 bg-red-500/10'
                : runtimeState === 'IDLE'
                  ? 'border-border text-gray-500 bg-background'
                  : 'border-blue-500/30 text-blue-400 bg-blue-500/10'
          }`}>
            {runtimeState}
          </div>
          <button onClick={reloadPreview} disabled={!url} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors" title="Refresh preview">
            <RotateCw className={`w-3.5 h-3.5 ${isReloading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={openPreview} disabled={!url} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors" title="Open preview in browser">
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      
      {/* Viewport */}
      <div className="flex-1 bg-white relative min-h-0">
        {url && iframeUrl ? (
            <iframe 
              key={runId}
              src={iframeUrl} 
              className="w-full h-full border-none bg-white"
              title="Preview"
              sandbox="allow-scripts allow-same-origin allow-forms"
            />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-panel text-gray-500 p-8 text-center">
            {state === 'FAILED' ? (
              <>
                <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                </div>
                <p className="text-[14px] font-semibold text-gray-200">Execution Failed</p>
                <p className="text-[12px] mt-2 text-red-400 max-w-sm">
                  {activities.slice(-1)[0]?.message || 'A fatal error occurred during runtime.'}
                </p>
                <div className="mt-6 w-full max-w-md bg-black/40 rounded-lg p-3 text-left border border-border/50">
                  <p className="text-[10px] text-gray-500 uppercase font-semibold mb-2">Last Terminal Output</p>
                  <p className="text-[11px] font-mono text-gray-300 break-all overflow-hidden h-16">
                  {(Array.isArray(lines) ? lines : []).slice(-3).map(l => l.text).join('\n') || 'No terminal logs captured.'}
                  </p>
                </div>
              </>
            ) : state === 'DISCONNECTED' || state === 'RECONNECTING' ? (
              <>
                <div className="w-12 h-12 rounded-xl bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center mb-4">
                  <WifiOff className="w-5 h-5 text-yellow-500" />
                </div>
                <p className="text-[14px] font-semibold text-gray-200">Connection Lost</p>
                <p className="text-[12px] mt-2 text-yellow-400 max-w-sm">
                  {state === 'RECONNECTING' 
                    ? 'Attempting to reconnect to the backend...'
                    : 'Backend connection unavailable.'}
                </p>
              </>
            ) : runtimeState !== 'IDLE' && runtimeState !== 'READY' && runtimeState !== 'FAILED' ? (
              <>
                <div className="w-12 h-12 rounded-xl bg-accent border border-border flex items-center justify-center mb-4">
                  <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                </div>
                <p className="text-[13px] font-medium text-gray-200">{runtimeState}</p>
                <p className="text-[12px] mt-1 text-gray-500">
                  {latestRuntimeLifecycleEvent?.message || 'Waiting for verified runtime readiness...'}
                </p>
              </>
            ) : (
              <>
                <div className="w-12 h-12 rounded-xl bg-accent border border-border flex items-center justify-center mb-4">
                  <Globe className="w-5 h-5 text-gray-400" />
                </div>
                <p className="text-[13px] font-medium text-gray-300">Preview Offline</p>
                <p className="text-[12px] mt-1 text-gray-500">Generate an app or wait for the runtime to become ready.</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
