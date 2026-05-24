import { useWorkspaceStore } from "../stores/workspace.store"
import { useAgentStore } from "../stores/agent.store"
import { Search, Activity, Wifi, Server, TerminalSquare, AlertTriangle } from "lucide-react"

export default function RuntimeInspector() {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const socketConnected = useAgentStore(s => s.socketConnected)
  const runtimeState = useAgentStore(s => s.runtimeState)
  const latestRuntimeLifecycleEvent = useAgentStore(s => s.latestRuntimeLifecycleEvent)
  const lastRuntimeError = useAgentStore(s => s.lastRuntimeError)

  if (!activeWorkspaceId) {
    return <div className="p-8 text-gray-500">No active workspace</div>
  }

  const port = latestRuntimeLifecycleEvent?.selectedPort ?? latestRuntimeLifecycleEvent?.requestedPort ?? "unassigned"
  const previewState = runtimeState
  const lastEventMessage = latestRuntimeLifecycleEvent?.message || "No runtime lifecycle event received."

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono overflow-y-auto">
      <div className="border-b border-[#333] px-6 py-4 flex items-center space-x-3 sticky top-0 bg-[#1e1e1e] z-10">
        <Search className="w-5 h-5 text-blue-400" />
        <h2 className="text-lg text-gray-100 font-medium">Runtime Inspector</h2>
      </div>

      <div className="p-6">
        <div className="grid grid-cols-2 gap-6 max-w-5xl">
          
          <div className="border border-[#333] rounded-md bg-[#252526] p-4">
            <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-4 flex items-center">
              <Activity className="w-4 h-4 mr-2" />
              Connection Status
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-[#333] pb-2">
                <span className="text-gray-500">Websocket</span>
                <span className={`flex items-center ${socketConnected ? "text-green-400" : "text-red-400"}`}>
                  <Wifi className="w-3 h-3 mr-1" /> {socketConnected ? "Connected" : "Disconnected"}
                </span>
              </div>
              <div className="flex justify-between border-b border-[#333] pb-2">
                <span className="text-gray-500">Sandbox Port</span>
                <span className="text-blue-400 font-bold">{port}</span>
              </div>
              <div className="flex justify-between pb-2">
                <span className="text-gray-500">Runtime Event</span>
                <span className="text-gray-300">{latestRuntimeLifecycleEvent?.type || "none"}</span>
              </div>
            </div>
          </div>

          <div className="border border-[#333] rounded-md bg-[#252526] p-4">
            <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-4 flex items-center">
              <Server className="w-4 h-4 mr-2" />
              Runtime State
            </h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-[#333] pb-2">
                <span className="text-gray-500">Preview</span>
                <span className={`font-bold ${
                  previewState === "READY"
                    ? "text-green-400"
                    : previewState === "FAILED"
                      ? "text-red-400"
                      : previewState === "IDLE"
                        ? "text-gray-400"
                        : "text-blue-400"
                }`}>{previewState}</span>
              </div>
              <div className="flex flex-col pb-2">
                <span className="text-gray-500 mb-1">Last Runtime Signal</span>
                <span className="text-gray-300 bg-[#1e1e1e] p-2 rounded border border-[#333]">
                  <TerminalSquare className="w-3 h-3 inline mr-2 text-gray-500" />
                  {lastEventMessage}
                </span>
              </div>
              {lastRuntimeError ? (
                <div className="flex flex-col pb-2">
                  <span className="text-gray-500 mb-1">Last Error</span>
                  <span className="text-red-400 bg-[#1e1e1e] p-2 rounded border border-red-900/40">
                    {lastRuntimeError.code}: {lastRuntimeError.message}
                  </span>
                </div>
              ) : null}
            </div>
          </div>

          <div className="col-span-2 border border-yellow-900/30 rounded-md bg-yellow-900/10 p-4">
            <h3 className="text-sm text-yellow-500/80 uppercase tracking-widest font-bold mb-2 flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2" />
              Inspector Console
            </h3>
            <div className="bg-[#1e1e1e] border border-[#333] h-32 rounded p-3 text-xs text-gray-500 flex flex-col font-mono overflow-y-auto">
              <div>[system] Runtime inspector attached to workspace {activeWorkspaceId}.</div>
              <div>[websocket] Subscribed to namespace: orchestration.</div>
              <div>[runtime] state={runtimeState}</div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
