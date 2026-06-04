import type { 
  WorkspaceMetadata, 
  ArtifactSnapshot,
  RunMetadata
} from "../stores/workspace.store"
import { ENV } from "../config/env"

const API_BASE = ENV.API_URL

async function requestWorkspace<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    let detail = body
    try {
      const parsed = JSON.parse(body)
      detail = parsed.detail || parsed.error || body
    } catch {
      // Keep raw response body.
    }
    throw new Error(detail || `Request failed with ${res.status}`)
  }
  return res.json()
}

export async function fetchWorkspaces(): Promise<WorkspaceMetadata[]> {
  return requestWorkspace<WorkspaceMetadata[]>("/workspaces")
}

export async function createWorkspace(name: string): Promise<WorkspaceMetadata> {
  return requestWorkspace<WorkspaceMetadata>("/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export async function updateWorkspace(workspaceId: string, name: string): Promise<WorkspaceMetadata> {
  return requestWorkspace<WorkspaceMetadata>(`/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  })
}

export async function duplicateWorkspace(workspaceId: string, name?: string): Promise<WorkspaceMetadata> {
  return requestWorkspace<WorkspaceMetadata>(`/workspaces/${workspaceId}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export async function archiveWorkspace(workspaceId: string): Promise<WorkspaceMetadata> {
  return requestWorkspace<WorkspaceMetadata>(`/workspaces/${workspaceId}`, {
    method: "DELETE",
  })
}

export type BrainDecision =
  | "local_only"
  | "local_plus_question"
  | "ask_user_before_generate"
  | "provider_required"
  | "provider_review_only"
  | "compose_cases"

export type BrainComplexity = "low" | "medium" | "high"
export type BrainRiskLevel = "low" | "medium" | "high"

export interface BrainDecisionResult {
  decision: BrainDecision
  confidence: number
  reason: string
  planning_required?: boolean
  signature: {
    domain: string
    intent: string
    app_type: string
    complexity: BrainComplexity
    feature_keywords: string[]
    required_capabilities: string[]
  }
  scope_analysis: {
    is_broad: boolean
    risk_level: BrainRiskLevel
    missing_decisions: Array<{
      key: string
      question: string
      default_recommendation: string
      risk: BrainRiskLevel
      options?: Array<{
        text: string
        score: number
        is_recommended: boolean
      }>
    }>
  }
  recommended_mvp: {
    title: string
    features: string[]
  }
  implementation_plan?: string[]
  task_list?: string[]
  matched_cases: unknown[]
  project_state?: Record<string, unknown> | null
  project_action?: Record<string, unknown> | null
  workspace_awareness?: Record<string, unknown> | null
  workspace_impact?: Record<string, unknown> | null
  change_scope?: {
    mode?: string
    project_type?: string
    change_type?: string
    scope_size?: "small" | "medium" | "large" | "unclear" | string
    impact_reason?: string
    changed_intent?: string
    affected_areas?: string[]
    target_files?: string[]
    estimated_affected_files?: number
    preserve_features?: string[]
    required_validation?: string[]
    clarifying_questions?: string[]
    should_ask_clarification?: boolean
    safe_to_patch_locally?: boolean
    confidence?: number
    [key: string]: unknown
  } | null
  subdomains?: Array<{
    name: string
    description: string
    entities?: Array<{
      name: string
      fields?: Array<{ name: string; type: string }>
    }>
  }>
  vertical_slices?: Array<{
    name: string
    description: string
    target_components?: string[]
    dependencies?: string[]
  }>
}

export async function runBrainPreflight(prompt: string, projectId?: string | null): Promise<BrainDecisionResult> {
  return requestWorkspace<BrainDecisionResult>("/brain/preflight", {
    method: "POST",
    body: JSON.stringify({ prompt, project_id: projectId ?? null }),
  })
}

export type PreflightHistoryAction =
  | "auto_continue"
  | "use_recommended_mvp"
  | "generate_anyway"

export type PreflightHistoryPayload = {
  original_prompt: string
  final_prompt: string
  action: PreflightHistoryAction
  decision: BrainDecisionResult["decision"]
  signature?: BrainDecisionResult["signature"] | null
  recommended_mvp?: BrainDecisionResult["recommended_mvp"] | null
  missing_decision_keys?: string[]
  workspace_id?: string | null
}

export type PreflightHistoryResponse = {
  ok: boolean
  record: {
    id: string
    schema_version: string
    created_at: string
    original_prompt: string
    final_prompt: string
    action: PreflightHistoryAction
    decision: BrainDecisionResult["decision"]
    signature?: BrainDecisionResult["signature"] | null
    recommended_mvp?: BrainDecisionResult["recommended_mvp"] | null
    missing_decision_keys: string[]
    workspace_id?: string | null
  }
}

export async function savePreflightHistory(
  payload: PreflightHistoryPayload
): Promise<PreflightHistoryResponse> {
  return requestWorkspace<PreflightHistoryResponse>("/brain/preflight/history", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function fetchWorkspaceRuns(workspaceId: string): Promise<RunMetadata[]> {
  const res = await fetch(`${API_BASE}/workspaces/${workspaceId}/runs`)
  if (!res.ok) throw new Error("Failed to fetch runs")
  return res.json()
}

export function buildWorkspaceTreeUrl(workspaceId: string, runId?: string | null): string {
  return runId
    ? `${API_BASE}/workspaces/${workspaceId}/repository-tree?run_id=${encodeURIComponent(runId)}`
    : `${API_BASE}/workspaces/${workspaceId}/repository-tree`
}

export async function fetchWorkspaceTree(workspaceId: string, runId?: string) {
  const url = buildWorkspaceTreeUrl(workspaceId, runId)
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch repository tree")
  const data = await res.json()
  return {
    ...data,
    tree: Array.isArray(data?.tree) ? data.tree : [],
    ecosystem: typeof data?.ecosystem === "string" ? data.ecosystem : "unknown",
    totalFiles: Number.isFinite(Number(data?.totalFiles)) ? Number(data.totalFiles) : 0,
    runId: typeof data?.runId === "string" ? data.runId : null,
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
  const params = new URLSearchParams({ path_id: pathId })
  if (runId) params.append("run_id", runId)
  const url = `${API_BASE}/workspaces/${workspaceId}/file?${params.toString()}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(await readErrorDetail(res, "Failed to fetch file content"))
  return res.json()
}

export interface SaveFileContentResponse {
  ok: boolean
  path: string
  pathId: string
  sizeBytes: number
  language: string
  updatedAt: number
  error: string | null
}

export async function saveFileContent(workspaceId: string, pathId: string, content: string, runId?: string): Promise<SaveFileContentResponse> {
  const params = new URLSearchParams({ path_id: pathId })
  if (runId) params.append("run_id", runId)
  const url = `/workspaces/${workspaceId}/file?${params.toString()}`
  return requestWorkspace<SaveFileContentResponse>(url, {
    method: "PUT",
    body: JSON.stringify({ content }),
  })
}

export interface WorkspaceEntryMutationResponse {
  ok: boolean
  path: string
  pathId: string
  name?: string
  type: "file" | "directory"
  sizeBytes?: number
  language?: string
  updatedAt?: number
  error: string | null
}

export async function createWorkspaceEntry(
  workspaceId: string,
  payload: { path: string; type: "file" | "directory"; content?: string },
  runId?: string | null,
): Promise<WorkspaceEntryMutationResponse> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  return requestWorkspace<WorkspaceEntryMutationResponse>(
    `/workspaces/${workspaceId}/entry${query ? `?${query}` : ""}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  )
}

export async function moveWorkspaceEntry(
  workspaceId: string,
  pathId: string,
  newPath: string,
  runId?: string | null,
): Promise<WorkspaceEntryMutationResponse> {
  const params = new URLSearchParams()
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  return requestWorkspace<WorkspaceEntryMutationResponse>(
    `/workspaces/${workspaceId}/entry${query ? `?${query}` : ""}`,
    {
      method: "PATCH",
      body: JSON.stringify({ path_id: pathId, new_path: newPath }),
    },
  )
}

export async function deleteWorkspaceEntry(
  workspaceId: string,
  pathId: string,
  runId?: string | null,
): Promise<WorkspaceEntryMutationResponse> {
  const params = new URLSearchParams({ path_id: pathId })
  if (runId) params.append("run_id", runId)
  return requestWorkspace<WorkspaceEntryMutationResponse>(`/workspaces/${workspaceId}/entry?${params.toString()}`, {
    method: "DELETE",
  })
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
  const params = new URLSearchParams({ path_id: pathId })
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
  const params = new URLSearchParams({ path_id: pathId })
  if (runId) params.append("run_id", runId)
  const query = params.toString()
  const url = `${API_BASE}/workspaces/${workspaceId}/regions?${query}`
  
  const res = await fetch(url)
  if (!res.ok) throw new Error("Failed to fetch regions")
  const data = await res.json()
  return Array.isArray(data) ? data : []
}

async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  const body = await res.text()
  if (!body) return fallback
  try {
    const parsed = JSON.parse(body)
    return parsed.detail || parsed.error || fallback
  } catch {
    return body || fallback
  }
}

export interface PatchMetadata {
  patch_type: string
  target_file?: string
  target_symbol?: string
  target_region: { start_line: number; end_line: number }
  grounding_context: unknown
  confidence_score: number
  locality: string
  blast_radius: string
}

export interface PatchesResponse {
  grounded_patches: PatchMetadata[]
  collision_reports: unknown[]
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
