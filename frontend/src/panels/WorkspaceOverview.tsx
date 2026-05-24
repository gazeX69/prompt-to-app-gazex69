import { useState, useEffect } from "react"
import { useWorkspaceStore } from "../stores/workspace.store"
import { fetchReadiness } from "../api/workspace.api"
import type { ExecutionReadiness } from "../api/workspace.api"
import { Activity, Clock, Server, Box, Cpu, ShieldCheck } from "lucide-react"

export default function WorkspaceOverview() {
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const runtimeSnapshot = useWorkspaceStore((s) => s.runtimeSnapshot)
  const repositorySnapshot = useWorkspaceStore((s) => s.repositorySnapshot)
  const runHistory = useWorkspaceStore((s) => s.runHistory)
  const activeRunId = useWorkspaceStore((s) => s.activeRunId)
  const loadRunData = useWorkspaceStore((s) => s.loadRunData)

  const [readiness, setReadiness] = useState<ExecutionReadiness | null>(null)

  useEffect(() => {
    if (!activeWorkspaceId) return
    fetchReadiness(activeWorkspaceId, activeRunId || undefined)
      .then(setReadiness)
      .catch(console.error)
  }, [activeWorkspaceId, activeRunId])

  const ws = activeWorkspaceId ? workspaces[activeWorkspaceId] : null

  if (!ws) {
    return <div className="p-8 text-gray-500">No active workspace</div>
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e1e] text-gray-300 font-mono overflow-y-auto">
      <div className="border-b border-[#333] px-6 py-4 flex items-center justify-between sticky top-0 bg-[#1e1e1e] z-10">
        <div className="flex items-center space-x-3">
          <Activity className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg text-gray-100 font-medium">Workspace Overview</h2>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-gray-500">Workspace ID:</span>
          <span className="text-gray-300 bg-[#333] px-2 py-1 rounded">{ws.id}</span>
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-5xl">
        
        {/* Core Info */}
        <div className="grid grid-cols-2 gap-6">
          <div className="border border-[#333] rounded-md bg-[#252526] p-4 flex flex-col justify-between">
            <div>
              <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-1">Repository</h3>
              <div className="text-2xl text-gray-100 font-sans tracking-tight mb-2">{ws.name}</div>
              <div className="text-xs text-gray-500 break-all">{ws.pathLabel}</div>
            </div>
            <div className="mt-4 flex items-center space-x-4 text-xs">
              <div className="flex items-center space-x-1">
                <Box className="w-3 h-3 text-blue-400" />
                <span>{repositorySnapshot ? repositorySnapshot.ecosystem : ws.ecosystem}</span>
              </div>
              <div className="flex items-center space-x-1">
                <Server className="w-3 h-3 text-green-400" />
                <span className="text-green-400 capitalize">{runtimeSnapshot ? runtimeSnapshot.orchestrationHealth : ws.runtimeHealth}</span>
              </div>
            </div>
          </div>

          <div className="border border-[#333] rounded-md bg-[#252526] p-4 flex flex-col justify-between">
            <div>
              <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-1">Activity</h3>
              <div className="text-3xl text-gray-100 font-sans tracking-tight mb-1">{ws.runCount} <span className="text-base text-gray-500">runs</span></div>
            </div>
            <div className="mt-4 flex items-center space-x-2 text-xs text-gray-500">
              <Clock className="w-3 h-3" />
              <span>Created: {new Date(ws.createdAt).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        {/* Workspace Timeline */}
        <div className="mt-8">
          <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-4 flex items-center">
            <Clock className="w-4 h-4 mr-2" />
            Recent Runs Timeline
          </h3>
          
          {runHistory.length === 0 ? (
             <div className="border border-[#333] rounded-md bg-[#252526] p-6 text-center text-sm text-gray-500">
               No run history available.
             </div>
          ) : (
            <div className="flex space-x-4 overflow-x-auto pb-4">
              {runHistory.slice(0, 5).map(run => {
                const isActive = run.run_id === activeRunId;
                return (
                  <div 
                    key={run.run_id}
                    onClick={() => { if (!isActive && activeWorkspaceId) loadRunData(activeWorkspaceId, run.run_id) }}
                    className={`shrink-0 w-48 border rounded-md p-3 cursor-pointer transition-colors ${isActive ? 'border-blue-500 bg-[#252526]' : 'border-[#333] bg-[#252526] hover:border-gray-500 hover:bg-[#2a2a2b]'}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-xs font-bold font-sans ${isActive ? 'text-blue-400' : 'text-gray-300'}`}>{run.run_id}</span>
                      {run.status === 'success' ? <div className="w-2 h-2 rounded-full bg-green-500" /> : <div className="w-2 h-2 rounded-full bg-red-500" />}
                    </div>
                    <div className="text-[10px] text-gray-500 mb-2 truncate">{new Date(run.startedAt).toLocaleString()}</div>
                    <div className="flex justify-between text-[10px]">
                      <span className="text-gray-400">Top/Seq:</span>
                      <span className="text-gray-300">{run.topologyScore?.toFixed(1) || '-'} / {run.sequencingScore?.toFixed(1) || '-'}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Live Runtime Metrics */}
        {runtimeSnapshot ? (
          <div>
            <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-3 flex items-center">
              <Cpu className="w-4 h-4 mr-2" />
              Live Telemetry
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <MetricCard 
                label="Sequencing Stability" 
                value={`${runtimeSnapshot.sequencingStabilityScore} / 10`} 
                highlight={runtimeSnapshot.sequencingStabilityScore > 8 ? 'good' : 'warning'}
              />
              <MetricCard 
                label="Topology Alignment" 
                value={`${runtimeSnapshot.topologyAlignmentScore} / 10`} 
                highlight={runtimeSnapshot.topologyAlignmentScore > 8 ? 'good' : 'warning'}
              />
              <MetricCard 
                label="Mutation Locality" 
                value={`${runtimeSnapshot.mutationLocalityScore} / 10`} 
                highlight={runtimeSnapshot.mutationLocalityScore > 8 ? 'good' : 'warning'}
              />
            </div>
          </div>
        ) : (
          <div className="border border-yellow-900/30 rounded-md bg-yellow-900/10 p-4 flex items-center space-x-3">
             <Activity className="w-4 h-4 text-yellow-500 animate-pulse" />
             <span className="text-sm text-yellow-500/80">Awaiting live telemetry from orchestration engine...</span>
          </div>
        )}

        {/* Execution Readiness Panel */}
        {readiness && (
          <div className="mt-8">
            <h3 className="text-sm text-gray-400 uppercase tracking-widest font-bold mb-3 flex items-center">
              <ShieldCheck className="w-4 h-4 mr-2" />
              Execution Readiness Freeze
            </h3>
            <div className={`border rounded-md p-6 ${
              readiness.execution_readiness_status === 'EXECUTION_READY' ? 'border-green-500/30 bg-green-500/5' :
              readiness.execution_readiness_status === 'LIMITED_READY' ? 'border-yellow-500/30 bg-yellow-500/5' :
              'border-[#333] bg-[#252526]'
            }`}>
              <div className="flex justify-between items-center mb-6">
                <div>
                  <div className="text-xs uppercase text-gray-500 font-bold mb-1">Status</div>
                  <div className={`text-2xl font-bold tracking-tight ${
                    readiness.execution_readiness_status === 'EXECUTION_READY' ? 'text-green-400' :
                    readiness.execution_readiness_status === 'LIMITED_READY' ? 'text-yellow-400' :
                    'text-gray-400'
                  }`}>
                    {readiness.execution_readiness_status.replace('_', ' ')}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs uppercase text-gray-500 font-bold mb-1">Readiness Score</div>
                  <div className="text-2xl font-bold text-gray-100">
                    {(readiness.execution_readiness_score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-4 gap-4">
                <MetricCard label="Patch Count" value={readiness.metrics.patch_count.toString()} highlight="good" />
                <MetricCard label="Replay Stability" value={`${(readiness.metrics.replay_stability * 100).toFixed(0)}%`} highlight={readiness.metrics.replay_stability > 0.8 ? 'good' : 'warning'} />
                <MetricCard label="Sim Confidence" value={`${(readiness.metrics.simulation_confidence * 100).toFixed(0)}%`} highlight={readiness.metrics.simulation_confidence > 0.8 ? 'good' : 'warning'} />
                <MetricCard label="Contract Freeze" value={readiness.contract_freeze_status} highlight={readiness.contract_freeze_status === 'locked' ? 'good' : 'danger'} />
              </div>
              <div className="mt-4 pt-4 border-t border-[#333] flex justify-between text-xs text-gray-500">
                <span>Orchestration Drift Audit: <span className="text-green-400 font-bold">{readiness.drift_audit_status.toUpperCase()}</span></span>
                <span>ENGINEERING_FREEZE.md enforced. Actual execution disabled.</span>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

function MetricCard({ label, value, highlight }: { label: string, value: string, highlight?: 'good' | 'warning' | 'danger' }) {
  const colorClass = 
    highlight === 'good' ? 'text-green-400' :
    highlight === 'warning' ? 'text-yellow-400' :
    highlight === 'danger' ? 'text-red-400' : 'text-blue-400';

  return (
    <div className="border border-[#333] rounded bg-[#252526] p-4 flex flex-col">
      <span className="text-xs uppercase tracking-widest text-gray-500 font-bold mb-2">{label}</span>
      <span className={`text-xl font-bold ${colorClass}`}>{value}</span>
    </div>
  )
}
