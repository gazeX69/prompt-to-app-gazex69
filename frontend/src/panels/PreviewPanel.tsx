import { useEffect, useMemo, useState } from 'react'
import { RotateCw, ExternalLink, Globe, AlertTriangle, WifiOff, Loader2, Square } from 'lucide-react'
import { usePreviewStore } from '../stores/preview.store'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'
import { useWorkspaceStore } from '../stores/workspace.store'
import { api } from '../services/api'

export default function PreviewPanel() {
  const { url, isReloading, refreshToken, hardRefresh, runtimeStatus, generationFailure, generationStatus, setRuntimeStatus, clear } = usePreviewStore()
  const { state, activities, runtimeState, latestRuntimeLifecycleEvent } = useAgentStore()
  const { lines } = useTerminalStore()
  const activeWorkspaceId = useWorkspaceStore((store) => store.activeWorkspaceId)
  
  const runId = usePreviewStore(state => state.runId) || 'legacy'
  const [iframeUrl, setIframeUrl] = useState('')
  const [isStopping, setIsStopping] = useState(false)

  const runtimeProjectId = useMemo(() => (
    runtimeStatus?.project_id
      || latestRuntimeLifecycleEvent?.workspaceId
      || activeWorkspaceId
      || null
  ), [activeWorkspaceId, latestRuntimeLifecycleEvent?.workspaceId, runtimeStatus?.project_id])

  useEffect(() => {
    if (!runtimeProjectId) return

    let cancelled = false
    const loadRuntimeStatus = async () => {
      try {
        const status = await api.get<any>(`/runtime/${runtimeProjectId}`, { timeout: 5000 })
        if (!cancelled) setRuntimeStatus(status)
      } catch {
        // Runtime ownership status is best-effort in the preview chrome.
      }
    }

    loadRuntimeStatus()
    const interval = window.setInterval(loadRuntimeStatus, 5000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [runtimeProjectId, setRuntimeStatus])

  useEffect(() => {
    if (url) {
      setIframeUrl(`${url}?run_id=${runId}&refresh=${refreshToken}&t=${Date.now()}`)
    } else {
      setIframeUrl('')
    }
  }, [url, runId, refreshToken])
  
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
    if (url) hardRefresh()
  }

  const openPreview = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
  }

  const stopRuntime = async () => {
    if (!runtimeProjectId || isStopping) return
    setIsStopping(true)
    try {
      const status = await api.post<any>(`/runtime/${runtimeProjectId}/stop`, {}, { timeout: 15000 })
      setRuntimeStatus(status)
      clear()
    } finally {
      setIsStopping(false)
    }
  }

  const ownerRun = runtimeStatus?.run_id || (runId !== 'legacy' ? runId : null)
  const ownerPort = runtimeStatus?.port ?? latestRuntimeLifecycleEvent?.selectedPort ?? latestRuntimeLifecycleEvent?.requestedPort
  const canStopRuntime = Boolean(runtimeProjectId && runtimeStatus?.status && runtimeStatus.status !== 'stopped' && runtimeStatus.status !== 'failed')
  const generationLabel = generationStatus
    ? `${generationStatus.status}${generationStatus.phase ? ` / ${generationStatus.phase}` : ''}`
    : null

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
            {displayUrl}{ownerPort ? ` · :${ownerPort}` : ''}{ownerRun ? ` · ${ownerRun}` : ''}{generationLabel ? ` · ${generationLabel}` : ''}
          </div>
        </div>
        
        <div className="flex items-center space-x-1 ml-4 shrink-0">
          <div className={`px-2 py-1 rounded border text-[10px] font-mono ${
            runtimeState === 'READY'
              || runtimeState === 'RUNNING'
              ? 'border-green-500/30 text-green-400 bg-green-500/10'
              : runtimeState === 'FAILED'
                ? 'border-red-500/30 text-red-400 bg-red-500/10'
                : runtimeState === 'IDLE'
                  ? 'border-border text-gray-500 bg-background'
                  : 'border-blue-500/30 text-blue-400 bg-blue-500/10'
          }`}>
            {runtimeState === 'READY' ? 'RUNNING' : runtimeState}
          </div>
          <button onClick={reloadPreview} disabled={!url} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors" title="Refresh preview">
            <RotateCw className={`w-3.5 h-3.5 ${isReloading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={openPreview} disabled={!url} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors" title="Open preview in browser">
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
          <button onClick={stopRuntime} disabled={!canStopRuntime || isStopping} className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed rounded transition-colors" title="Stop runtime">
            {isStopping ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
      
      {/* Viewport */}
      <div className="flex-1 bg-white relative min-h-0">
        {url && iframeUrl ? (
            <iframe 
              key={`${runId}:${refreshToken}`}
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
                <p className="text-[14px] font-semibold text-gray-200">
                  {generationFailure ? 'Generation Failed Before Runtime' : 'Execution Failed'}
                </p>
                <p className="text-[12px] mt-2 text-red-400 max-w-sm">
                  {generationFailure
                    ? `${generationFailure.stage}: ${generationFailure.message}`
                    : activities.slice(-1)[0]?.message || 'A fatal error occurred during runtime.'}
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
            ) : runtimeState !== 'IDLE' && runtimeState !== 'READY' && runtimeState !== 'RUNNING' && runtimeState !== 'FAILED' && runtimeState !== 'STOPPED' ? (
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
                <p className="text-[12px] mt-1 text-gray-500">
                  {generationStatus?.status === 'accepted' || generationStatus?.status === 'generating'
                    ? generationStatus.message || 'Generation is running in the background.'
                    : 'Generate an app or wait for the runtime to become ready.'}
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
