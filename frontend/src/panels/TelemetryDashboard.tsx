import { useState, useEffect, useCallback } from "react"
import { Activity, Cpu, Clock, Coins, Trash2, RotateCw, CheckCircle2, XCircle, ChevronDown, ChevronUp, AlertCircle, Sparkles, Server } from "lucide-react"
import { ENV } from "../config/env"

interface ProviderStats {
  provider_name: string
  provider_type: string
  model: string
  calls: number
  success_rate: number
  avg_latency_ms: number
  total_tokens: number
  cost: number
}

interface TelemetryStats {
  total_calls: number
  success_rate: number
  avg_latency_ms: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_cost: number
  total_saved_usd: number
  failover_count: number
  providers: ProviderStats[]
}

interface TelemetryLog {
  id: number
  timestamp: string
  provider_id: string
  provider_name: string
  provider_type: string
  model: string
  latency_ms: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost: number
  status: "success" | "failed"
  error_message?: string
  system_prompt?: string
  user_prompt?: string
  response?: string
}

export default function TelemetryDashboard() {
  const [stats, setStats] = useState<TelemetryStats | null>(null)
  const [logs, setLogs] = useState<TelemetryLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [filterStatus, setFilterStatus] = useState<"all" | "success" | "failed">("all")

  const fetchTelemetryData = useCallback(async () => {
    setError(null)
    try {
      // Fetch stats
      const statsRes = await fetch(`${ENV.API_URL}/settings/telemetry/stats`)
      if (!statsRes.ok) throw new Error("Failed to load telemetry stats")
      const statsData = await statsRes.json()
      setStats(statsData)

      // Fetch logs
      const logsRes = await fetch(`${ENV.API_URL}/settings/telemetry/logs?limit=50`)
      if (!logsRes.ok) throw new Error("Failed to load telemetry logs")
      const logsData = await logsRes.json()
      setLogs(logsData)
    } catch (e) {
      console.error(e)
      setError("Failed to fetch telemetry data from backend.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTelemetryData()
  }, [fetchTelemetryData])

  // Auto refresh every 5 seconds if checked
  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(() => {
      fetchTelemetryData()
    }, 5000)
    return () => clearInterval(timer)
  }, [autoRefresh, fetchTelemetryData])

  const handleClearTelemetry = async () => {
    if (!window.confirm("Are you sure you want to clear all telemetry logs? This will reset all cost and token statistics.")) return
    setLoading(true)
    try {
      const res = await fetch(`${ENV.API_URL}/settings/telemetry/logs`, {
        method: "DELETE",
      })
      if (!res.ok) throw new Error("Failed to clear telemetry logs")
      await fetchTelemetryData()
    } catch (e) {
      console.error(e)
      alert("Failed to clear logs.")
      setLoading(false)
    }
  }

  const getProviderTypeBadgeClass = (type: string) => {
    switch (type) {
      case "qwen": return "bg-purple-500/10 text-purple-400 border-purple-500/20"
      case "openai": return "bg-green-500/10 text-green-400 border-green-500/20"
      case "gemini": return "bg-blue-500/10 text-blue-400 border-blue-500/20"
      case "anthropic": return "bg-amber-500/10 text-amber-400 border-amber-500/20"
      default: return "bg-gray-500/10 text-gray-400 border-gray-500/20"
    }
  }

  const formatTimestamp = (isoString: string) => {
    try {
      const date = new Date(isoString.replace(" ", "T") + "Z")
      return date.toLocaleTimeString() + " " + date.toLocaleDateString()
    } catch (e) {
      return isoString
    }
  }

  const filteredLogs = logs.filter(log => {
    if (filterStatus === "all") return true
    return log.status === filterStatus
  })

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-10">
      {/* Action Header */}
      <div className="flex flex-wrap justify-between items-center gap-4 bg-gradient-to-r from-[#0E0E12] to-[#0A0A0C] p-5 rounded-xl border border-white/[0.05] shadow-[0_4px_24px_rgba(0,0,0,0.3)]">
        <div>
          <h3 className="text-xs font-bold text-gray-200 uppercase tracking-[0.18em] flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-500 animate-pulse" />
            Observability & Telemetry Metrics
          </h3>
          <p className="text-[11px] text-gray-400 mt-1.5 leading-relaxed font-sans">
            Real-time insights on AI provider usage, response latency, token consumption, and estimated costs.
          </p>
        </div>
        <div className="flex items-center gap-3.5 shrink-0">
          <label className="flex items-center gap-2 text-xs text-gray-400 font-semibold cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded bg-[#09090C] border-white/[0.08] text-blue-500 focus:ring-0 focus:ring-offset-0"
            />
            Auto-refresh (5s)
          </label>
          <button
            onClick={fetchTelemetryData}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.06] hover:border-white/[0.12] px-3 text-xs font-semibold text-gray-300 transition duration-150 active:scale-95"
          >
            <RotateCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={handleClearTelemetry}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-red-500/20 hover:border-red-500/40 text-red-400 hover:bg-red-500/10 px-3 text-xs font-semibold transition duration-150 active:scale-95"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear Statistics
          </button>
        </div>
      </div>

      {error && (
        <div className="border border-red-500/25 bg-red-500/5 p-4 rounded-xl text-red-400 text-xs flex items-start gap-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span className="font-sans leading-relaxed">{error}</span>
        </div>
      )}

      {/* Summary Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Card 1: Total Calls */}
          <div className="border border-white/[0.04] bg-[#0E0E12] p-4.5 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.2)] flex flex-col justify-between relative overflow-hidden transition-all duration-300 hover:border-white/[0.08]">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Total LLM Calls</span>
              <div className="p-1.5 rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">
                <Cpu className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="mt-4">
              <span className="text-2xl font-bold font-mono text-gray-200">{stats.total_calls}</span>
              <div className="text-[10px] text-gray-500 mt-1 font-medium font-sans">Across all instances</div>
            </div>
          </div>

          {/* Card 2: Success Rate */}
          <div className="border border-white/[0.04] bg-[#0E0E12] p-4.5 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.2)] flex flex-col justify-between relative overflow-hidden transition-all duration-300 hover:border-white/[0.08]">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Success Rate</span>
              <div className="p-1.5 rounded-md bg-green-500/10 text-green-400 border border-green-500/20">
                <CheckCircle2 className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="mt-4">
              <span className="text-2xl font-bold font-mono text-gray-200">{(stats.success_rate * 100).toFixed(1)}%</span>
              <div className="mt-2.5 w-full bg-[#1c1c24] h-1.5 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${stats.success_rate > 0.95 ? "bg-green-500" : stats.success_rate > 0.8 ? "bg-yellow-500" : "bg-red-500"}`} 
                  style={{ width: `${stats.success_rate * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* Card 3: Avg Latency */}
          <div className="border border-white/[0.04] bg-[#0E0E12] p-4.5 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.2)] flex flex-col justify-between relative overflow-hidden transition-all duration-300 hover:border-white/[0.08]">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Avg Latency</span>
              <div className="p-1.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
                <Clock className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="mt-4">
              <span className="text-2xl font-bold font-mono text-gray-200">{(stats.avg_latency_ms / 1000).toFixed(2)}s</span>
              <div className="text-[10px] text-gray-500 mt-1 font-medium font-sans">{stats.avg_latency_ms} ms mean</div>
            </div>
          </div>

          {/* Card 4: Total Tokens */}
          <div className="border border-white/[0.04] bg-[#0E0E12] p-4.5 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.2)] flex flex-col justify-between relative overflow-hidden transition-all duration-300 hover:border-white/[0.08]">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-gray-500 tracking-wider">Total Tokens</span>
              <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <Activity className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="mt-3">
              <span className="text-2xl font-bold font-mono text-gray-200">{(stats.total_tokens / 1000).toFixed(1)}K</span>
              <div className="flex items-center justify-between text-[9px] text-gray-500 mt-1.5 font-sans font-medium">
                <span>In: {(stats.total_prompt_tokens / 1000).toFixed(1)}K</span>
                <span>Out: {(stats.total_completion_tokens / 1000).toFixed(1)}K</span>
              </div>
            </div>
          </div>

          {/* Card 5: Estimated Cost & Saved */}
          <div className="border border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-transparent p-4.5 rounded-xl shadow-[0_4px_20px_rgba(59,130,246,0.06)] flex flex-col justify-between relative overflow-hidden transition-all duration-300 hover:border-blue-500/35">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-blue-300 tracking-wider">Estimated Cost</span>
              <div className="p-1.5 rounded-md bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                <Coins className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="mt-3">
              <div className="text-xl font-bold font-mono text-gray-100">${stats.total_cost.toFixed(4)}</div>
              {stats.total_saved_usd > 0 && (
                <div className="inline-flex items-center gap-1.5 bg-green-500/10 border border-green-500/20 rounded-full px-2.5 py-0.5 mt-1.5 text-[9px] font-bold text-green-400 leading-none">
                  <Sparkles className="w-2.5 h-2.5" />
                  Saved ${stats.total_saved_usd.toFixed(4)}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Provider breakdown table */}
      {stats && stats.providers && stats.providers.length > 0 && (
        <div className="border border-white/[0.04] bg-[#0E0E12] p-5 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.25)] space-y-4">
          <h4 className="text-xs font-bold text-gray-200 uppercase tracking-widest flex items-center gap-2">
            <Server className="w-4 h-4 text-blue-400" />
            AI Agent breakdown performance
          </h4>
          <div className="overflow-x-auto rounded-lg border border-white/[0.03]">
            <table className="w-full text-xs text-left text-gray-400">
              <thead className="text-[9px] uppercase bg-[#14141A] text-gray-400 border-b border-white/[0.04]">
                <tr>
                  <th scope="col" className="px-5 py-3">Agent Name</th>
                  <th scope="col" className="px-5 py-3">Model</th>
                  <th scope="col" className="px-5 py-3 text-center">Calls</th>
                  <th scope="col" className="px-5 py-3 text-center">Success Rate</th>
                  <th scope="col" className="px-5 py-3 text-center">Avg Latency</th>
                  <th scope="col" className="px-5 py-3 text-center">Total Tokens</th>
                  <th scope="col" className="px-5 py-3 text-right">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03] bg-[#0E0E12]">
                {stats.providers.map((p, idx) => (
                  <tr key={idx} className="hover:bg-white/[0.02] transition font-mono border-b border-white/[0.02] last:border-b-0">
                    <td className="px-5 py-3 font-sans font-semibold text-gray-200">
                      <div className="flex items-center gap-2">
                        <span>{p.provider_name}</span>
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase ${getProviderTypeBadgeClass(p.provider_type)}`}>
                          {p.provider_type}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-300">{p.model}</td>
                    <td className="px-5 py-3 text-center text-gray-300">{p.calls}</td>
                    <td className="px-5 py-3 text-center">
                      <span className={`font-semibold ${p.success_rate >= 0.95 ? "text-green-400" : p.success_rate >= 0.8 ? "text-yellow-400" : "text-red-400"}`}>
                        {(p.success_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-5 py-3 text-center text-gray-300">{(p.avg_latency_ms / 1000).toFixed(2)}s</td>
                    <td className="px-5 py-3 text-center text-gray-300">{(p.total_tokens / 1000).toFixed(1)}K</td>
                    <td className="px-5 py-3 text-right font-bold text-gray-200">
                      {p.provider_type === "local" ? (
                        <span className="text-green-400 text-[9px] font-bold bg-green-500/10 px-2 py-0.5 rounded border border-green-500/20">FREE</span>
                      ) : (
                        `$${p.cost.toFixed(4)}`
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Failovers Warning Panel */}
      {stats && stats.failover_count > 0 && (
        <div className="border border-yellow-500/20 bg-yellow-500/5 p-4 rounded-xl flex items-start gap-3 shadow-[0_4px_16px_rgba(234,179,8,0.05)]">
          <AlertCircle className="w-5 h-5 text-yellow-500 mt-0.5 shrink-0" />
          <div className="text-xs">
            <h4 className="font-bold text-yellow-500 uppercase tracking-wider">Failover Auto-Switch Events</h4>
            <p className="text-yellow-300/80 mt-1 leading-relaxed font-sans">
              The system experienced <strong>{stats.failover_count}</strong> automatic switches/failovers due to provider outages or credentials failure. View system console alerts for specific transition details.
            </p>
          </div>
        </div>
      )}

      {/* Logs Feed */}
      <div className="border border-white/[0.04] bg-[#0E0E12] p-5 rounded-xl shadow-[0_4px_24px_rgba(0,0,0,0.25)] space-y-4">
        <div className="flex justify-between items-center flex-wrap gap-3 pb-2 border-b border-white/[0.04]">
          <h4 className="text-xs font-bold text-gray-200 uppercase tracking-widest">Recent LLM completion logs</h4>
          <div className="flex gap-2">
            {(["all", "success", "failed"] as const).map(s => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                className={`px-3 py-1 rounded-lg text-[9px] font-bold uppercase border transition duration-150 ${
                  filterStatus === s 
                    ? "bg-blue-600/10 border-blue-500/35 text-blue-400 shadow-[0_0_12px_rgba(59,130,246,0.1)]"
                    : "border-white/[0.06] text-gray-400 hover:bg-white/[0.02]"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8 text-xs text-gray-500 font-sans">Loading logs feed...</div>
        ) : filteredLogs.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-8 font-sans">No matching telemetry logs found.</p>
        ) : (
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
            {filteredLogs.map(log => {
              const isExpanded = expandedLogId === log.id
              return (
                <div 
                  key={log.id} 
                  className={`border rounded-lg transition-all duration-200 bg-[#14141A] overflow-hidden ${
                    isExpanded ? "shadow-md" : ""
                  } ${
                    log.status === "success" 
                      ? "border-white/[0.03] hover:border-white/[0.08]" 
                      : "border-red-500/20 hover:border-red-500/40"
                  }`}
                >
                  {/* Log Header Row */}
                  <div 
                    onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                    className="p-3.5 flex items-center justify-between gap-4 cursor-pointer select-none text-xs hover:bg-white/[0.02]"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center flex-wrap gap-2">
                        {log.status === "success" ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                        )}
                        <span className="font-bold text-gray-200">{log.provider_name}</span>
                        <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[8px] font-bold uppercase ${getProviderTypeBadgeClass(log.provider_type)}`}>
                          {log.provider_type}
                        </span>
                        <span className="text-[10px] text-gray-500 font-mono">{log.model}</span>
                      </div>
                      <div className="mt-1.5 text-gray-500 font-mono text-[10px] truncate max-w-xl">
                        {log.status === "success" 
                          ? `Response: ${log.response || ""}`
                          : `Error: ${log.error_message || ""}`
                        }
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-4.5 shrink-0 font-mono text-[10px] text-gray-400">
                      <span>{(log.latency_ms / 1000).toFixed(2)}s</span>
                      <span>{log.total_tokens}T</span>
                      <span className="w-16 text-right font-bold text-gray-200">
                        {log.provider_type === "local" ? "FREE" : `$${log.cost.toFixed(4)}`}
                      </span>
                      <span className="text-gray-500 shrink-0">
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </span>
                    </div>
                  </div>

                  {/* Expanded Detail Panel */}
                  {isExpanded && (
                    <div className="border-t border-white/[0.04] bg-[#0E0E12]/50 p-4.5 space-y-4 font-mono text-[11px] text-gray-300">
                      <div className="flex justify-between items-center text-[10px] text-gray-500 border-b border-white/[0.04] pb-2">
                        <span>Timestamp: {formatTimestamp(log.timestamp)}</span>
                        <span>Log ID: #{log.id}</span>
                      </div>

                      {log.status === "failed" && log.error_message && (
                        <div className="bg-red-500/10 border border-red-500/20 text-red-300 p-3.5 rounded-lg">
                          <div className="font-bold text-[10px] text-red-400 uppercase mb-1.5">Execution Failure:</div>
                          {log.error_message}
                        </div>
                      )}

                      {log.system_prompt && (
                        <div className="space-y-1.5">
                          <div className="font-bold text-[10px] text-gray-500 uppercase tracking-wider">System Prompt:</div>
                          <pre className="bg-[#09090C] p-3.5 border border-white/[0.04] rounded-lg overflow-x-auto max-h-[150px] whitespace-pre-wrap select-text text-gray-400 leading-relaxed">
                            {log.system_prompt}
                          </pre>
                        </div>
                      )}

                      {log.user_prompt && (
                        <div className="space-y-1.5">
                          <div className="font-bold text-[10px] text-gray-500 uppercase tracking-wider">User Prompt:</div>
                          <pre className="bg-[#09090C] p-3.5 border border-white/[0.04] rounded-lg overflow-x-auto max-h-[250px] whitespace-pre-wrap select-text text-gray-300 leading-relaxed">
                            {log.user_prompt}
                          </pre>
                        </div>
                      )}

                      {log.status === "success" && log.response && (
                        <div className="space-y-1.5">
                          <div className="font-bold text-[10px] text-blue-400 uppercase tracking-wider">Completion Response:</div>
                          <pre className="bg-[#09090C] p-3.5 border border-blue-500/15 rounded-lg overflow-x-auto max-h-[300px] whitespace-pre-wrap select-text text-blue-200 leading-relaxed shadow-[inset_0_1px_12px_rgba(59,130,246,0.02)]">
                            {log.response}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
