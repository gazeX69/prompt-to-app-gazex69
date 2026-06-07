import { useEffect, useMemo, useState } from "react"
import { Activity, AlertTriangle, Bug, Database, FileJson, GitBranch, Package, RefreshCw, Server, ToggleLeft, ToggleRight } from "lucide-react"
import { fetchDebugObservatory, type ObservatorySnapshot } from "../api/workspace.api"
import { useWorkspaceStore } from "../stores/workspace.store"

const STORAGE_KEY = "debug-observatory-enabled"

export default function DebugObservatory() {
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId)
  const [enabled, setEnabled] = useState(() => localStorage.getItem(STORAGE_KEY) === "true")
  const [snapshot, setSnapshot] = useState<ObservatorySnapshot | null>(null)
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle")
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    if (!activeWorkspaceId || !enabled) return
    setStatus("loading")
    try {
      const data = await fetchDebugObservatory(activeWorkspaceId)
      setSnapshot(data)
      setError(null)
      setStatus("idle")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load observatory snapshot.")
      setStatus("error")
    }
  }

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(enabled))
    if (!enabled) return
    void refresh()
    const timer = window.setInterval(() => void refresh(), 3000)
    return () => window.clearInterval(timer)
  }, [enabled, activeWorkspaceId])

  const stateFlow = snapshot?.state_flow ?? []
  const errorItems = snapshot?.error_center ?? []
  const stateFiles = useMemo(() => Object.entries(snapshot?.state_files ?? {}), [snapshot])
  const dependencyHealth = snapshot?.dependency_health

  if (!activeWorkspaceId) {
    return <div className="p-8 text-gray-500">No active workspace</div>
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-[#1e1e1e] text-gray-300">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#333] bg-[#1e1e1e] px-6 py-4">
        <div className="flex items-center gap-3">
          <Bug className="h-5 w-5 text-blue-400" />
          <div>
            <h2 className="text-lg font-medium text-gray-100">Debug Observatory</h2>
            <p className="text-xs text-gray-500">Unified AI agent state snapshot</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setEnabled((value) => !value)}
            className={`inline-flex h-9 items-center gap-2 rounded-md border px-3 text-xs font-semibold transition ${
              enabled
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                : "border-white/10 bg-white/[0.03] text-gray-400"
            }`}
          >
            {enabled ? <ToggleRight className="h-4 w-4" /> : <ToggleLeft className="h-4 w-4" />}
            Enable Observatory
          </button>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={!enabled || status === "loading"}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs font-semibold text-gray-300 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <RefreshCw className={`h-4 w-4 ${status === "loading" ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {!enabled ? (
        <div className="p-6">
          <div className="rounded-md border border-[#333] bg-[#252526] p-5 text-sm text-gray-400">
            Observatory is off. Enable it to start live refresh every 3 seconds.
          </div>
        </div>
      ) : (
        <div className="space-y-5 p-6">
          {error && (
            <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="Discovery State" icon={<GitBranch className="h-4 w-4" />}>
              <KeyValue label="Session ID" value={snapshot?.discovery_state.session_id || "missing"} />
              <KeyValue label="Current Node" value={snapshot?.discovery_state.current_node || "missing"} />
              <KeyValue label="Completed" value={String(snapshot?.discovery_state.completed ?? false)} />
              <JsonBlock value={snapshot?.discovery_state.answers ?? {}} />
              <JsonBlock title="Draft State" value={snapshot?.discovery_state.draft_state ?? {}} />
            </Section>

            <Section title="Project State" icon={<Database className="h-4 w-4" />}>
              <KeyValue label="project_type" value={snapshot?.project_state.project_type || "unknown"} />
              <KeyValue label="domain" value={snapshot?.project_state.domain || "unknown"} />
              <KeyValue label="database" value={snapshot?.project_state.database || "unknown"} />
              <KeyValue label="supplier" value={String(snapshot?.project_state.supplier ?? "unknown")} />
              <KeyValue label="source" value={snapshot?.project_state.source || "missing"} />
              <KeyValue label="last_updated" value={snapshot?.project_state.last_updated || "missing"} />
            </Section>
          </div>

          <Section title="State Flow Visualization" icon={<Activity className="h-4 w-4" />}>
            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              {stateFlow.map((stage) => (
                <div key={stage.stage} className="rounded-md border border-[#333] bg-[#1e1e1e] p-3">
                  <div className="text-xs font-bold text-gray-200">{stage.stage}</div>
                  <StatusBadge status={stage.status} />
                  <div className="mt-2 truncate text-[11px] text-gray-500">{stage.detail || "no detail"}</div>
                </div>
              ))}
            </div>
          </Section>

          <Section title="Dependency Health" icon={<Package className="h-4 w-4" />}>
            <div className="grid gap-3 md:grid-cols-4">
              <Metric label="Status" value={dependencyHealth?.status || "unknown"} />
              <Metric label="Detected" value={String(dependencyHealth?.detected_imports?.length ?? 0)} />
              <Metric label="Declared" value={String(dependencyHealth?.declared_dependencies?.length ?? 0)} />
              <Metric label="Missing" value={String(dependencyHealth?.missing_dependencies?.length ?? 0)} />
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              <JsonBlock title="Detected Imports" value={dependencyHealth?.detected_imports ?? []} />
              <JsonBlock title="Declared Dependencies" value={dependencyHealth?.declared_dependencies ?? []} />
              <JsonBlock title="Missing Dependencies" value={dependencyHealth?.missing_dependencies ?? []} />
              <JsonBlock title="Repair Strategy" value={dependencyHealth?.repair_strategy ?? []} />
            </div>
            <KeyValue label="repair_result" value={dependencyHealth?.repair_result || "unknown"} />
          </Section>

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="Generator Context" icon={<Server className="h-4 w-4" />}>
              <KeyValue label="generation_mode" value={snapshot?.generator_context.generation_mode || "unknown"} />
              <KeyValue label="loaded_contract" value={snapshot?.generator_context.loaded_contract?.app_type || "missing"} />
              <KeyValue label="contract_version" value={snapshot?.generator_context.loaded_contract?.contract_version || "missing"} />
              <div>
                <div className="mb-1 text-[10px] uppercase tracking-widest text-gray-500">final prompt</div>
                <div className="max-h-28 overflow-y-auto rounded border border-[#333] bg-[#1a1a1d] p-2 text-xs text-gray-300">
                  {snapshot?.generator_context.final_prompt || "missing"}
                </div>
              </div>
              <JsonBlock title="Project State Used" value={snapshot?.generator_context.project_state_used ?? {}} />
            </Section>

            <Section title="Error Center" icon={<AlertTriangle className="h-4 w-4" />}>
              {errorItems.length === 0 ? (
                <div className="text-sm text-gray-500">No build, runtime, reflection, or preview errors detected.</div>
              ) : (
                <div className="space-y-2">
                  {errorItems.map((item, index) => (
                    <div key={`${item.source}-${index}`} className="rounded border border-red-500/20 bg-red-500/10 p-3 text-xs">
                      <div className="mb-1 font-bold text-red-200">{item.source} / {item.stage}{item.code ? ` / ${item.code}` : ""}</div>
                      <div className="text-red-100/80">{item.message}</div>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          </div>

          <Section title="State File Inspector" icon={<FileJson className="h-4 w-4" />}>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {stateFiles.map(([key, file]) => (
                <div key={key} className="rounded-md border border-[#333] bg-[#1e1e1e] p-3">
                  <div className="text-xs font-bold text-gray-200">{key}</div>
                  <div className="mt-1 truncate text-[11px] text-gray-500">{file.path}</div>
                  <StatusBadge status={file.exists ? "loaded" : "missing"} />
                  <div className="mt-2 text-[11px] text-gray-500">
                    {file.last_modified ? new Date(file.last_modified * 1000).toLocaleString() : "no modified time"}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}
    </div>
  )
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-md border border-[#333] bg-[#252526] p-4">
      <h3 className="mb-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-gray-400">
        {icon}
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-[#333] pb-2 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="truncate font-mono text-gray-200">{value}</span>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#333] bg-[#1e1e1e] p-3">
      <div className="text-[10px] font-bold uppercase tracking-widest text-gray-500">{label}</div>
      <div className="mt-2 truncate font-mono text-sm text-gray-100">{value}</div>
    </div>
  )
}

function JsonBlock({ title = "Answers", value }: { title?: string; value: unknown }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-widest text-gray-500">{title}</div>
      <pre className="max-h-40 overflow-y-auto rounded border border-[#333] bg-[#1a1a1d] p-2 text-xs text-gray-300">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const style =
    status === "loaded"
      ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
      : status === "failed"
        ? "border-red-500/30 bg-red-500/10 text-red-300"
        : status === "missing"
          ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-300"
          : "border-gray-500/30 bg-gray-500/10 text-gray-300"
  return <span className={`mt-2 inline-flex rounded border px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest ${style}`}>{status}</span>
}
