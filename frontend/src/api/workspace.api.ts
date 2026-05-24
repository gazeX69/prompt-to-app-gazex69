import type { 
  WorkspaceMetadata, 
  ArtifactSnapshot,
  RunMetadata
} from "../stores/workspace.store"

const API_BASE = "http://127.0.0.1:8000" // adjust according to environment later

export async function fetchWorkspaces(): Promise<WorkspaceMetadata[]> {
  const res = await fetch(`${API_BASE}/workspaces`)
  if (!res.ok) throw new Error("Failed to fetch workspaces")
  return res.json()
}

export async function fetchWorkspaceRuns(workspaceId: string): Promise<RunMetadata[]> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/runs`)
  if (!res.ok) throw new Error("Failed to fetch runs")
  return res.json()
}

export async function fetchWorkspaceTree(workspaceId: string, runId?: string) {
  const url = runId ? `${API_BASE}/workspaces/${workspaceId}/repository-tree?run_id=${runId}` : `${API_BASE}/workspaces/${workspaceId}/repository-tree`
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch repository tree")
  const data = await res.json()
  return {
    ...data,
    tree: Array.isArray(data?.tree) ? data.tree : [],
    ecosystem: typeof data?.ecosystem === "string" ? data.ecosystem : "unknown",
    totalFiles: Number.isFinite(Number(data?.totalFiles)) ? Number(data.totalFiles) : 0,
  }
}

export async function fetchArtifacts(workspaceId: string, runId?: string): Promise<ArtifactSnapshot[]> {
  const url = runId ? `${API_BASE}/workspaces/${workspaceId}/artifacts?run_id=${runId}` : `${API_BASE}/workspaces/${workspaceId}/artifacts`
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch artifacts")
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export async function fetchArtifactContent(workspaceId: string, artifactId: string, runId?: string): Promise<{content: string, truncated: boolean, error: string | null}> {
  const url = runId ? `${API_BASE}/workspaces/${workspaceId}/artifacts/${artifactId}?run_id=${runId}` : `${API_BASE}/workspaces/${workspaceId}/artifacts/${artifactId}`
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch artifact content")
  return res.json()
}

export async function fetchFileContent(workspaceId: string, pathId: string, runId?: string): Promise<{content: string, sizeBytes: number, language: string, truncated: boolean, error: string | null}> {
  const url = runId ? `${API_BASE}/workspaces/${workspaceId}/file?path_id=${pathId}&run_id=${runId}` : `${API_BASE}/workspaces/${workspaceId}/file?path_id=${pathId}`
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch file content")
  return res.json()
}

export interface SymbolMetadata {
  name: string
  type: 'import' | 'export' | 'component' | 'function' | 'class'
  filePath: string
  exported: boolean
  referencedCount: number
}

export async function fetchSymbols(workspaceId: string, runId?: string, pathId?: string): Promise<SymbolMetadata[]> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  if (pathId) params.append("path_id", pathId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/symbols${query ? `?${query}` : ''}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch symbols")
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export interface ReferenceMetadata {
  imports: string[]
  imported_by: string[]
  dependency_depth: number
  ownership_chain: string[]
  mutation_heat: string
  blast_radius_score: 'isolated' | 'local' | 'shared' | 'critical'
}

export async function fetchReferences(workspaceId: string, pathId: string, runId?: string): Promise<ReferenceMetadata> {
  const params = new URLSearchParams()
  params.append("path_id", pathId)
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/references?${query}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch references")
  const data = await res.json()
  return {
    imports: Array.isArray(data?.imports) ? data.imports : [],
    imported_by: Array.isArray(data?.imported_by) ? data.imported_by : [],
    dependency_depth: Number.isFinite(Number(data?.dependency_depth)) ? Number(data.dependency_depth) : 0,
    ownership_chain: Array.isArray(data?.ownership_chain) ? data.ownership_chain : [],
    mutation_heat: typeof data?.mutation_heat === "string" ? data.mutation_heat : "unknown",
    blast_radius_score: ["isolated", "local", "shared", "critical"].includes(data?.blast_radius_score)
      ? data.blast_radius_score
      : "isolated",
  }
}

export interface RegionMetadata {
  type: string
  name?: string
  start_line: number
  end_line: number
}

export async function fetchRegions(workspaceId: string, pathId: string, runId?: string): Promise<RegionMetadata[]> {
  const params = new URLSearchParams()
  params.append("path_id", pathId)
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/regions?${query}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch regions")
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

export interface PatchMetadata {
  patch_type: string
  target_file?: string
  target_symbol?: string
  target_region: { start_line: number; end_line: number }
  grounding_context: any
  confidence_score: number
  locality: string
  blast_radius: string
}

export interface PatchesResponse {
  grounded_patches: PatchMetadata[]
  collision_reports: any[]
  confidence_scores: number[]
  region_maps_generated: boolean
}

export async function fetchPatches(workspaceId: string, runId?: string): Promise<PatchesResponse> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/patches${query ? `?${query}` : ''}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch patches")
  const data = await res.json()
  return {
    grounded_patches: Array.isArray(data?.grounded_patches) ? data.grounded_patches : [],
    collision_reports: Array.isArray(data?.collision_reports) ? data.collision_reports : [],
    confidence_scores: Array.isArray(data?.confidence_scores) ? data.confidence_scores : [],
    region_maps_generated: Boolean(data?.region_maps_generated),
  }
}

export interface ReplayReport {
  patch_id: string
  replay_safety: 'safe' | 'degraded' | 'unsafe'
  drift_state: string
  stale_warning: boolean
  relocated_region: { start_line: number; end_line: number }
  relocation_confidence: number
  stability_score: number
  duplicate_injection_detected: boolean
  replay_generation: number
}

export interface ReplaysResponse {
  replay_reports: ReplayReport[]
  stale_patch_warnings: ReplayReport[]
  system_stability: number
}

export async function fetchReplays(workspaceId: string, runId?: string): Promise<ReplaysResponse> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/replays${query ? `?${query}` : ''}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch replays")
  const data = await res.json()
  return {
    replay_reports: Array.isArray(data?.replay_reports) ? data.replay_reports : [],
    stale_patch_warnings: Array.isArray(data?.stale_patch_warnings) ? data.stale_patch_warnings : [],
    system_stability: Number.isFinite(Number(data?.system_stability)) ? Number(data.system_stability) : 0,
  }
}

export interface SimulationReport {
  patch_id: string
  status: 'applied' | 'skipped'
  skipped_reasons: string[]
  before_line_count: number
  after_line_count: number
  changed_regions: { start_line: number; end_line: number; type: string }[]
  syntax_sanity: {
    passed: boolean
    balance: { braces: number; brackets: number; parens: number }
  }
  simulation_confidence_score: number
}

export interface SimulationsResponse {
  simulation_reports: SimulationReport[]
  system_simulation_confidence: number
}

export async function fetchSimulations(workspaceId: string, runId?: string): Promise<SimulationsResponse> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/simulations${query ? `?${query}` : ''}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch simulations")
  const data = await res.json()
  return {
    simulation_reports: Array.isArray(data?.simulation_reports) ? data.simulation_reports : [],
    system_simulation_confidence: Number.isFinite(Number(data?.system_simulation_confidence)) ? Number(data.system_simulation_confidence) : 0,
  }
}

export interface ExecutionReadiness {
  execution_readiness_score: number
  execution_readiness_status: string
  metrics: {
    replay_stability: number
    simulation_confidence: number
    patch_count: number
  }
  drift_audit_status: string
  contract_freeze_status: string
}

export async function fetchReadiness(workspaceId: string, runId?: string): Promise<ExecutionReadiness> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/readiness${query ? `?${query}` : ''}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch readiness")
  return res.json()
}
