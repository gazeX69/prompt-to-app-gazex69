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
  return res.json()
}

export async function fetchArtifacts(workspaceId: string, runId?: string): Promise<ArtifactSnapshot[]> {
  const url = runId ? `${API_BASE}/workspaces/${workspaceId}/artifacts?run_id=${runId}` : `${API_BASE}/workspaces/${workspaceId}/artifacts`
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch artifacts")
  return res.json()
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
  return res.json()
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
  return res.json()
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
  return res.json()
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
  return res.json()
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
  return res.json()
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
  return res.json()
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
