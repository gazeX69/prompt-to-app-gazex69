import { useState, useEffect } from "react"
import { useWorkspaceStore } from "../stores/workspace.store"
import { fetchReadiness } from "../api/workspace.api"
import type { ExecutionReadiness } from "../api/workspace.api"
import { Activity, Clock, Server, Box, Cpu, ShieldCheck } from "lucide-react"
import { ENV } from "../config/env"

export default function WorkspaceOverview() {
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const workspaces = useWorkspaceStore((s) => s.workspaces)
  const runtimeSnapshot = useWorkspaceStore((s) => s.runtimeSnapshot)
  const repositorySnapshot = useWorkspaceStore((s) => s.repositorySnapshot)
  const runHistory = useWorkspaceStore((s) => s.runHistory)
  const activeRunId = useWorkspaceStore((s) => s.activeRunId)
  const loadRunData = useWorkspaceStore((s) => s.loadRunData)

  const [readiness, setReadiness] = useState<ExecutionReadiness | null>(null)
  const [reliability, setReliability] = useState<{ availability: number; mtbf_hours: number; total_failures: number } | null>(null)

  useEffect(() => {
    if (!activeWorkspaceId) return
    fetchReadiness(activeWorkspaceId, activeRunId || undefined)
      .then(setReadiness)
      .catch(console.error)
  }, [activeWorkspaceId, activeRunId])

  useEffect(() => {
    fetch(`${ENV.API_URL}/settings/reliability`)
      .then((res) => {
        if (!res.ok) throw new Error("Network response was not ok")
        return res.json()
      })
      .then(setReliability)
      .catch(console.error)
  }, [])

  const ws = activeWorkspaceId ? workspaces[activeWorkspaceId] : null

  if (!ws) {
    return <div className="p-8 text-gray-500 font-sans">No active workspace</div>
  }

  return (
    <div className="flex flex-col h-full bg-[#030304] text-gray-300 font-sans overflow-y-auto selection:bg-blue-500/30">
      <div className="border-b border-[#1a1a22] px-6 py-4 flex items-center justify-between sticky top-0 bg-[#08080a] z-10 shadow-sm">
        <div className="flex items-center space-x-3">
          <Activity className="w-5 h-5 text-blue-400" />
          <h2 className="text-base text-gray-100 font-bold tracking-wide">Workspace Overview</h2>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-gray-500 font-medium">Workspace ID:</span>
          <span className="text-gray-300 bg-[#09090C] border border-white/[0.04] px-2.5 py-1 rounded-md font-mono text-[10px] font-bold">{ws.id}</span>
        </div>
      </div>

      <div className="p-6 space-y-6 max-w-5xl mx-auto w-full">
        
        {/* Core Info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="border border-white/[0.04] rounded-xl bg-[#0E0E12] p-5 flex flex-col justify-between shadow-sm relative overflow-hidden">
            <div>
              <h3 className="text-[10px] text-gray-500 uppercase tracking-[0.2em] font-bold mb-2">Repository</h3>
              <div className="text-xl font-bold text-gray-100 tracking-wide mb-1">{ws.name}</div>
              <div className="text-xs text-gray-500 break-all font-mono leading-relaxed mt-2">{ws.pathLabel}</div>
            </div>
            <div className="mt-6 flex items-center space-x-4 text-xs font-semibold">
              <div className="flex items-center space-x-1.5 bg-blue-500/10 border border-blue-500/20 px-2.5 py-1 rounded-lg text-blue-400">
                <Box className="w-3.5 h-3.5" />
                <span>{repositorySnapshot ? repositorySnapshot.ecosystem : ws.ecosystem}</span>
              </div>
              <div className="flex items-center space-x-1.5 bg-green-500/10 border border-green-500/20 px-2.5 py-1 rounded-lg text-green-400">
                <Server className="w-3.5 h-3.5" />
                <span className="capitalize">{runtimeSnapshot ? runtimeSnapshot.orchestrationHealth : ws.runtimeHealth}</span>
              </div>
            </div>
          </div>

          <div className="border border-white/[0.04] rounded-xl bg-[#0E0E12] p-5 flex flex-col justify-between shadow-sm relative overflow-hidden">
            <div>
              <h3 className="text-[10px] text-gray-500 uppercase tracking-[0.2em] font-bold mb-2">Activity</h3>
              <div className="text-3xl font-bold text-gray-100 tracking-tight font-sans">
                {ws.runCount} <span className="text-xs text-gray-500 uppercase font-bold tracking-wider font-sans ml-1">runs executed</span>
              </div>
            </div>
            <div className="mt-6 flex items-center space-x-2 text-xs text-gray-500 font-medium font-sans">
              <Clock className="w-3.5 h-3.5" />
              <span>Created: {new Date(ws.createdAt).toLocaleDateString()}</span>
            </div>
          </div>
        </div>

        {/* Workspace Timeline */}
        <div className="pt-2">
          <h3 className="text-xs font-bold text-gray-200 uppercase tracking-widest mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-blue-400 animate-pulse" />
            Recent Runs Timeline
          </h3>
          
          {runHistory.length === 0 ? (
             <div className="border border-white/[0.04] rounded-xl bg-[#0E0E12] p-8 text-center text-xs text-gray-500 font-sans shadow-sm">
               No run history available. Run an AI generation first.
             </div>
          ) : (
             <div className="flex space-x-4 overflow-x-auto pb-4 scrollbar-thin">
               {runHistory.slice(0, 5).map(run => {
                 const isActive = run.run_id === activeRunId;
                 return (
                   <div 
                     key={run.run_id}
                     onClick={() => { if (!isActive && activeWorkspaceId) loadRunData(activeWorkspaceId, run.run_id) }}
                     className={`shrink-0 w-52 border rounded-xl p-4 cursor-pointer transition-all duration-200 shadow-sm ${
                       isActive 
                         ? 'border-blue-500/40 bg-[#0E0E12]/80 shadow-[0_4px_16px_rgba(59,130,246,0.08)]' 
                         : 'border-white/[0.04] bg-[#0E0E12] hover:border-white/[0.08] hover:bg-[#0E0E12]/50'
                     }`}
                   >
                     <div className="flex items-center justify-between mb-2">
                       <span className={`text-xs font-bold font-mono ${isActive ? 'text-blue-400' : 'text-gray-300'}`}>{run.run_id}</span>
                       <span className={`h-2 w-2 rounded-full ${run.status === 'success' ? 'bg-green-500' : 'bg-red-500'}`} />
                     </div>
                     <div className="text-[10px] text-gray-500 mb-3 font-mono">{new Date(run.startedAt).toLocaleString()}</div>
                     <div className="flex justify-between items-center text-[10px] font-mono border-t border-white/[0.03] pt-2">
                       <span className="text-gray-500 font-bold uppercase tracking-wider text-[8px]">Top / Seq</span>
                       <span className="text-gray-300 font-semibold">{run.topologyScore?.toFixed(1) || '-'} / {run.sequencingScore?.toFixed(1) || '-'}</span>
                     </div>
                   </div>
                 )
               })}
             </div>
          )}
        </div>

        {/* Live Runtime Metrics */}
        {runtimeSnapshot && (
          <div className="pt-2">
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-widest mb-4 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-400 animate-pulse" />
              Live Telemetry
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
        )}

        {reliability && (
          <div className="pt-2">
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-widest mb-4 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-green-400" />
              System Reliability Telemetry
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <MetricCard 
                label="System Availability" 
                value={`${(reliability.availability * 100).toFixed(2)}%`} 
                highlight={reliability.availability > 0.95 ? 'good' : 'warning'}
              />
              <MetricCard 
                label="MTBF (Mean Time Between Failures)" 
                value={`${reliability.mtbf_hours.toFixed(1)} hrs`} 
                highlight={reliability.mtbf_hours > 12 ? 'good' : 'warning'}
              />
              <MetricCard 
                label="Total Failed Generations" 
                value={`${reliability.total_failures} runs`} 
                highlight={reliability.total_failures === 0 ? 'good' : 'warning'}
              />
            </div>
          </div>
        )}

        {/* Execution Readiness Panel */}
        {readiness && (
          <div className="pt-2">
            <h3 className="text-xs font-bold text-gray-200 uppercase tracking-widest mb-4 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-blue-400" />
              Execution Readiness Freeze
            </h3>
            <div className={`border rounded-xl p-5 shadow-sm space-y-5 ${
              readiness.execution_readiness_status === 'EXECUTION_READY' ? 'border-green-500/20 bg-green-500/5' :
              readiness.execution_readiness_status === 'LIMITED_READY' ? 'border-yellow-500/20 bg-yellow-500/5' :
              'border-white/[0.04] bg-[#0E0E12]'
            }`}>
              <div className="flex justify-between items-center pb-3 border-b border-white/[0.04]">
                <div>
                  <div className="text-[9px] uppercase text-gray-500 font-bold tracking-wider">Freeze Status</div>
                  <div className={`text-xl font-bold tracking-wide mt-1 ${
                    readiness.execution_readiness_status === 'EXECUTION_READY' ? 'text-green-400' :
                    readiness.execution_readiness_status === 'LIMITED_READY' ? 'text-yellow-400' :
                    'text-gray-400'
                  }`}>
                    {readiness.execution_readiness_status.replace('_', ' ')}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[9px] uppercase text-gray-500 font-bold tracking-wider">Readiness Score</div>
                  <div className="text-xl font-bold text-gray-100 font-mono mt-1">
                    {(readiness.execution_readiness_score * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <MetricCard label="Patch Count" value={readiness.metrics.patch_count.toString()} highlight="good" />
                <MetricCard label="Replay Stability" value={`${(readiness.metrics.replay_stability * 100).toFixed(0)}%`} highlight={readiness.metrics.replay_stability > 0.8 ? 'good' : 'warning'} />
                <MetricCard label="Sim Confidence" value={`${(readiness.metrics.simulation_confidence * 100).toFixed(0)}%`} highlight={readiness.metrics.simulation_confidence > 0.8 ? 'good' : 'warning'} />
                <MetricCard label="Contract Freeze" value={readiness.contract_freeze_status} highlight={readiness.contract_freeze_status === 'locked' ? 'good' : 'danger'} />
              </div>
              <div className="mt-2 flex flex-wrap justify-between text-[10px] text-gray-500 font-mono font-medium leading-relaxed">
                <span>Orchestration Drift Audit: <span className="text-green-400 font-bold uppercase">{readiness.drift_audit_status}</span></span>
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
    <div className="border border-white/[0.04] rounded-xl bg-[#0E0E12] p-4 flex flex-col justify-between shadow-sm relative overflow-hidden">
      <span className="text-[9px] uppercase tracking-wider text-gray-500 font-bold mb-2 font-sans">{label}</span>
      <span className={`text-lg font-bold font-mono ${colorClass}`}>{value}</span>
    </div>
  )
}
