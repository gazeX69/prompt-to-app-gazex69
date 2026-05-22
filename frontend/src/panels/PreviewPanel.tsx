import { RotateCw, ExternalLink, Globe, AlertTriangle } from 'lucide-react'
import { usePreviewStore } from '../stores/preview.store'
import { useAgentStore } from '../stores/agent.store'
import { useTerminalStore } from '../stores/terminal.store'

export default function PreviewPanel() {
  const { url, isReloading } = usePreviewStore()
  const { state, activities } = useAgentStore()
  const { lines } = useTerminalStore()


  return (
    <div className="flex flex-col h-full bg-background border-l border-border min-w-0">
      {/* Browser Chrome */}
      <div className="h-12 border-b border-border bg-panel flex items-center px-3 shrink-0">
        <div className="flex space-x-1.5 mr-4 shrink-0">
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 hover:bg-red-500 transition-colors" />
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 hover:bg-yellow-500 transition-colors" />
          <div className="w-2.5 h-2.5 rounded-full bg-gray-700 hover:bg-green-500 transition-colors" />
        </div>
        
        <div className="flex-1 flex justify-center min-w-0">
          <div className="w-full max-w-[300px] h-7 bg-background border border-border rounded flex items-center justify-center px-2 text-[11px] text-gray-400 truncate">
            {url ? new URL(url).hostname : 'localhost:3000'}
          </div>
        </div>
        
        <div className="flex items-center space-x-1 ml-4 shrink-0">
          <button className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent rounded transition-colors">
            <RotateCw className={`w-3.5 h-3.5 ${isReloading ? 'animate-spin' : ''}`} />
          </button>
          <button className="p-1.5 text-gray-500 hover:text-gray-200 hover:bg-accent rounded transition-colors">
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      
      {/* Viewport */}
      <div className="flex-1 bg-white relative min-h-0">
        {url ? (
          <iframe 
            src={url} 
            className="w-full h-full border-none bg-white"
            title="Preview"
            sandbox="allow-scripts allow-same-origin allow-forms"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-panel text-gray-500 p-8 text-center">
            {state === 'failed' ? (
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
                    {lines.slice(-3).map(l => l.text).join('\n') || 'No terminal logs captured.'}
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="w-12 h-12 rounded-xl bg-accent border border-border flex items-center justify-center mb-4">
                  <Globe className="w-5 h-5 text-gray-400" />
                </div>
                <p className="text-[13px] font-medium text-gray-300">Preview Offline</p>
                <p className="text-[12px] mt-1 text-gray-500">Waiting for dev server...</p>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
