import { useCallback, useState, useEffect } from "react"
import { useWorkspaceStore } from "../stores/workspace.store"
import type { RepositoryFileNode } from "../stores/workspace.store"
import { fetchFileContent, fetchSymbols, fetchReferences, fetchRegions, fetchPatches, fetchReplays, fetchSimulations } from "../api/workspace.api"
import type { SymbolMetadata, ReferenceMetadata, RegionMetadata, PatchMetadata, ReplayReport, SimulationReport } from "../api/workspace.api"
import { FileCode, Code, Tag, Hash, Box, ArrowRight, ShieldAlert, GitMerge, Layout, AlertTriangle, FileDiff, Pencil } from "lucide-react"
import type { WorkspaceMode } from "../stores/workspace.store"

interface FileInspectorProps {
  file: RepositoryFileNode
  onSymbolClick: (filePath: string) => void
  onViewChange: (view: WorkspaceMode) => void
}

export default function FileInspector({ file, onSymbolClick, onViewChange }: FileInspectorProps) {
  const activeWorkspaceId = useWorkspaceStore(s => s.activeWorkspaceId)
  const activeRunId = useWorkspaceStore(s => s.activeRunId)
  const openFileInEditor = useWorkspaceStore(s => s.openFileInEditor)
  const editorDirty = useWorkspaceStore(s => s.editorDirty)
  const filePath = typeof file?.path === "string" ? file.path : ""
  const pathId = typeof file?.pathId === "string" ? file.pathId : ""
  const fileName = typeof file?.name === "string" ? file.name : "Unknown file"
  
  const [content, setContent] = useState("")
  const [sizeBytes, setSizeBytes] = useState(0)
  const [language, setLanguage] = useState("")
  const [truncated, setTruncated] = useState(false)
  const [fileLoaded, setFileLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [symbols, setSymbols] = useState<SymbolMetadata[]>([])
  const [references, setReferences] = useState<ReferenceMetadata | null>(null)
  const [regions, setRegions] = useState<RegionMetadata[]>([])
  const [patches, setPatches] = useState<(PatchMetadata & { replay?: ReplayReport, simulation?: SimulationReport })[]>([])
  
  useEffect(() => {
    if (!activeWorkspaceId || !filePath) {
      return
    }
    
    setContent("")
    setSizeBytes(0)
    setLanguage("")
    setTruncated(false)
    setFileLoaded(false)
    setError(null)
    setSymbols([])
    setReferences(null)
    setRegions([])
    setPatches([])

    if (!pathId) {
      setError("File metadata is missing a path identifier.")
      return
    }
    
    fetchFileContent(activeWorkspaceId, pathId, activeRunId || undefined)
      .then(res => {
        setContent(typeof res?.content === "string" ? res.content : "")
        setSizeBytes(Number.isFinite(Number(res?.sizeBytes)) ? Number(res.sizeBytes) : 0)
        setLanguage(typeof res?.language === "string" ? res.language : "")
        setTruncated(Boolean(res?.truncated))
        setFileLoaded(true)
        if (res.error) setError(res.error)
      })
      .catch(e => {
        setFileLoaded(false)
        setError(e.message)
      })
      
    fetchSymbols(activeWorkspaceId, activeRunId || undefined, pathId)
      .then(res => {
        setSymbols(Array.isArray(res) ? res : [])
      })
      .catch(console.error)

    fetchReferences(activeWorkspaceId, pathId, activeRunId || undefined)
      .then(res => {
        setReferences(res)
      })
      .catch(console.error)
      
    fetchRegions(activeWorkspaceId, pathId, activeRunId || undefined)
      .then(res => {
        setRegions(Array.isArray(res) ? res : [])
      })
      .catch(console.error)

    Promise.all([
      fetchPatches(activeWorkspaceId, activeRunId || undefined),
      fetchReplays(activeWorkspaceId, activeRunId || undefined),
      fetchSimulations(activeWorkspaceId, activeRunId || undefined)
    ]).then(([patchRes, replayRes, simRes]) => {
      const groundedPatches = Array.isArray(patchRes?.grounded_patches) ? patchRes.grounded_patches : []
      const replayReports = Array.isArray(replayRes?.replay_reports) ? replayRes.replay_reports : []
      const simulationReports = Array.isArray(simRes?.simulation_reports) ? simRes.simulation_reports : []
      const filePatches = groundedPatches.filter(p => filePath.endsWith(p.target_file || '') || p.target_file === filePath)
      
      const enrichedPatches = filePatches.map((p, i) => {
        const patchId = p.patch_type + `_${i}`
        const replay = replayReports.find(r => r.patch_id === patchId)
        const simulation = simulationReports.find(r => r.patch_id === patchId)
        return { ...p, replay, simulation }
      })
      
      setPatches(enrichedPatches)
    }).catch(console.error)
      
  }, [activeWorkspaceId, activeRunId, file, filePath, pathId])

  const safeSymbols = Array.isArray(symbols) ? symbols : []
  const safeRegions = Array.isArray(regions) ? regions : []
  const safePatches = Array.isArray(patches) ? patches : []
  const importedBy = Array.isArray(references?.imported_by) ? references.imported_by : []
  const ownershipChain = Array.isArray(references?.ownership_chain) ? references.ownership_chain : []
  const imports = safeSymbols.filter((s: SymbolMetadata) => s.type === 'import')
  const exports = safeSymbols.filter((s: SymbolMetadata) => s.exported && s.type !== 'import')
  const components = safeSymbols.filter((s: SymbolMetadata) => s.type === 'component')
  const functions = safeSymbols.filter((s: SymbolMetadata) => s.type === 'function')
  const displayError = error || (!filePath ? "File metadata is missing a path." : null)
  const editorBlockReason = !pathId
    ? "This file cannot be edited because its path identifier is missing."
    : truncated
      ? "This file cannot be edited because the loaded content is truncated."
      : displayError
  const canOpenInEditor = Boolean(fileLoaded && !displayError && !truncated && filePath && pathId)
  const handleOpenInEditor = useCallback(() => {
    if (!canOpenInEditor) {
      if (editorBlockReason) setError(editorBlockReason)
      return
    }
    if (editorDirty && !window.confirm("Discard unsaved editor changes and open this file?")) {
      setError("Open in Editor canceled. Unsaved editor changes were kept.")
      return
    }
    openFileInEditor({
      name: fileName,
      path: filePath,
      pathId,
      language: language || undefined,
    }, content, activeWorkspaceId || "", activeRunId)
    onViewChange("edit")
  }, [
    activeRunId,
    activeWorkspaceId,
    canOpenInEditor,
    content,
    editorBlockReason,
    editorDirty,
    fileName,
    filePath,
    language,
    onViewChange,
    openFileInEditor,
    pathId,
  ])
  
  return (
    <div className="flex h-full bg-[#1e1e1e] text-gray-300 font-mono">
      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-[#333]">
        <div className="border-b border-[#333] px-6 py-4 flex items-center justify-between bg-[#1e1e1e] shrink-0">
          <div className="flex items-center space-x-3 truncate">
            <FileCode className="w-5 h-5 text-blue-400 shrink-0" />
            <div className="truncate">
              <h2 className="text-lg text-gray-100 font-medium truncate">{fileName}</h2>
              <p className="text-xs text-gray-500 truncate">{filePath || 'Missing file path'}</p>
            </div>
          </div>
          <div className="flex items-center space-x-4 shrink-0 pl-4">
            {language && <span className="px-2 py-1 rounded text-[10px] bg-blue-500/20 text-blue-400 uppercase tracking-widest border border-blue-500/30">{language}</span>}
            {file.isEntrypoint && <span className="px-2 py-1 rounded text-[10px] bg-green-500/20 text-green-400 uppercase tracking-widest border border-green-500/30">Entry</span>}
            <span className="text-xs text-gray-500">{(sizeBytes / 1024).toFixed(1)} KB</span>
          </div>
        </div>
        
        {displayError ? (
          <div className="p-6 text-red-400 text-sm flex items-start space-x-2">
            <ShieldAlert className="w-5 h-5 shrink-0" />
            <span>Failed to load file: {displayError}</span>
          </div>
        ) : (
          <div className="flex-1 overflow-auto p-4 bg-[#1e1e1e]">
            {truncated && (
              <div className="mb-4 p-3 bg-yellow-900/20 border border-yellow-700 rounded text-yellow-500 text-sm">
                File exceeds maximum load size. Content has been truncated.
              </div>
            )}
            <pre className="text-sm font-mono text-gray-300 leading-relaxed overflow-visible">
              <code>{content || "Loading content..."}</code>
            </pre>
          </div>
        )}
      </div>
      
      {/* Sidebar Metadata */}
      <div className="w-80 flex flex-col bg-[#252526] shrink-0 overflow-y-auto">
        <div className="p-4 border-b border-[#333]">
          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Inspection</h3>

          <button
            type="button"
            onClick={handleOpenInEditor}
            disabled={!canOpenInEditor}
            title={editorBlockReason || "Open in Editor"}
            className="mb-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded border border-blue-400/30 bg-blue-500/10 px-3 text-sm font-medium text-blue-200 transition hover:bg-blue-500/15 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Pencil className="h-4 w-4" />
            Open in Editor
          </button>
          
          <div className="space-y-3">
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Ownership</span>
              <span className="text-purple-400">{references ? (ownershipChain.length > 0 ? ownershipChain.join(" ") : 'None') : (file.ownershipLabel || 'None')}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Blast Radius</span>
              <span className={`${
                  references?.blast_radius_score === 'critical' ? 'text-red-500 font-bold' :
                  references?.blast_radius_score === 'shared' ? 'text-yellow-500' :
                  references?.blast_radius_score === 'local' ? 'text-blue-500' :
                  'text-gray-500'
                }`}>
                {references?.blast_radius_score?.toUpperCase() || 'UNKNOWN'}
              </span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Dep Depth</span>
              <span className="text-blue-400">{references?.dependency_depth ?? '-'}</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Imported By</span>
              <span className="text-blue-400">{importedBy.length} files</span>
            </div>
          </div>
        </div>
        
        {references && importedBy.length > 0 && (
          <div className="p-4 border-b border-[#333]">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Cross-References</h3>
            <div className="text-[10px] uppercase text-gray-500 mb-2 flex items-center"><GitMerge className="w-3 h-3 mr-1" /> Imported By</div>
            <div className="space-y-1">
              {importedBy.map((path: string, i: number) => (
                <div key={i} className="text-xs text-blue-300 truncate cursor-pointer hover:text-blue-100 hover:underline flex items-center" onClick={() => onSymbolClick(path)} title={path}>
                  <ArrowRight className="w-3 h-3 mr-1 opacity-50 shrink-0" /> <span className="truncate">{path}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {safeRegions.length > 0 && (
          <div className="p-4 border-b border-[#333]">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Detected Regions</h3>
            <div className="space-y-2">
              {safeRegions.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <div className="flex items-center text-gray-300">
                    <Layout className="w-3 h-3 mr-1.5 text-gray-500" />
                    <span className="capitalize">{String(r.type || 'unknown').replace('_', ' ')}</span>
                    {r.name && <span className="ml-1 text-gray-500">({r.name})</span>}
                  </div>
                  <span className="text-gray-500 font-mono">L{r.start_line}-L{r.end_line}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {safePatches.length > 0 && (
          <div className="p-4 border-b border-[#333]">
            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Pending Patches (Dry Run)</h3>
            <div className="space-y-3">
              {safePatches.map((p, i) => (
                <div key={i} className="border border-green-500/20 bg-green-500/5 rounded p-2 text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-green-400 font-bold">{p.patch_type}</span>
                    <span className={p.confidence_score > 0.8 ? 'text-green-300' : 'text-yellow-400'}>
                      {(p.confidence_score * 100).toFixed(0)}% Conf
                    </span>
                  </div>
                    <div className="text-gray-400">Target: L{p.target_region?.start_line ?? '-'}-L{p.target_region?.end_line ?? '-'}</div>
                  {p.target_symbol && <div className="text-gray-500 mt-1">Symbol: {p.target_symbol}</div>}
                  
                  {p.replay && (
                    <div className={`mt-2 p-2 rounded text-xs flex flex-col space-y-1 ${
                      p.replay.replay_safety === 'unsafe' ? 'bg-red-500/10 border border-red-500/20' :
                      p.replay.replay_safety === 'degraded' ? 'bg-yellow-500/10 border border-yellow-500/20' :
                      'bg-blue-500/10 border border-blue-500/20'
                    }`}>
                      <div className="flex items-center justify-between font-bold">
                        <span className="flex items-center">
                          {p.replay.stale_warning && <AlertTriangle className="w-3 h-3 mr-1 text-red-400" />}
                          Replay State: {p.replay.replay_safety.toUpperCase()}
                        </span>
                        <span>Gen {p.replay.replay_generation}</span>
                      </div>
                      <div className="flex justify-between text-gray-400">
                        <span>Drift: {p.replay.drift_state}</span>
                        <span>Stability: {(p.replay.stability_score * 100).toFixed(0)}%</span>
                      </div>
                      {p.replay.drift_state === 'shifted' && (
                        <div className="text-blue-400">
                          Relocated: L{p.replay.relocated_region?.start_line ?? '-'}-L{p.replay.relocated_region?.end_line ?? '-'} ({(p.replay.relocation_confidence * 100).toFixed(0)}% Conf)
                        </div>
                      )}
                      {p.replay.duplicate_injection_detected && (
                        <div className="text-red-400">Duplicate Injection Detected!</div>
                      )}
                    </div>
                  )}
                  
                  {p.simulation && (
                    <div className={`mt-2 p-2 rounded text-xs flex flex-col space-y-1 ${
                      p.simulation.status === 'skipped' ? 'bg-gray-500/10 border border-gray-500/20' :
                      'bg-indigo-500/10 border border-indigo-500/20'
                    }`}>
                      <div className="flex items-center justify-between font-bold">
                        <span className="flex items-center">
                          <FileDiff className="w-3 h-3 mr-1 text-indigo-400" />
                          Sim Status: {p.simulation.status.toUpperCase()}
                        </span>
                        {p.simulation.status === 'applied' && (
                          <span className={p.simulation.syntax_sanity?.passed ? 'text-green-400' : 'text-red-400'}>
                            {p.simulation.syntax_sanity?.passed ? 'Syntax: PASS' : 'Syntax: FAIL'}
                          </span>
                        )}
                      </div>
                      
                      {p.simulation.status === 'skipped' ? (
                        <div className="text-gray-400">
                          Reasons: {Array.isArray(p.simulation.skipped_reasons) ? p.simulation.skipped_reasons.join(', ') : 'No skip reason provided'}
                        </div>
                      ) : (
                        <>
                          <div className="flex justify-between text-gray-400">
                            <span>Lines: {p.simulation.before_line_count} → {p.simulation.after_line_count}</span>
                            <span>Conf: {(p.simulation.simulation_confidence_score * 100).toFixed(0)}%</span>
                          </div>
                          {!p.simulation.syntax_sanity?.passed && (
                            <div className="text-red-400">
                              Imbalance: {JSON.stringify(p.simulation.syntax_sanity?.balance || {})}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="p-4 flex-1">
          <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Symbols</h3>
          
          <div className="space-y-6">
            {components.length > 0 && (
              <div>
                <div className="text-[10px] uppercase text-gray-500 mb-2 flex items-center"><Box className="w-3 h-3 mr-1" /> Components</div>
                <div className="space-y-1">
                  {components.map((s: SymbolMetadata, i: number) => (
                    <div key={i} className="text-sm text-blue-300 truncate cursor-pointer hover:text-blue-100 hover:underline flex items-center" onClick={() => onSymbolClick(s.filePath)}>
                      <ArrowRight className="w-3 h-3 mr-1 opacity-50" /> {s.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {exports.length > 0 && (
              <div>
                <div className="text-[10px] uppercase text-gray-500 mb-2 flex items-center"><Tag className="w-3 h-3 mr-1" /> Exports</div>
                <div className="space-y-1">
                  {exports.map((s: SymbolMetadata, i: number) => (
                    <div key={i} className="text-sm text-yellow-300 truncate cursor-pointer hover:text-yellow-100 hover:underline flex items-center" onClick={() => onSymbolClick(s.filePath)}>
                      <ArrowRight className="w-3 h-3 mr-1 opacity-50" /> {s.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {functions.length > 0 && (
              <div>
                <div className="text-[10px] uppercase text-gray-500 mb-2 flex items-center"><Code className="w-3 h-3 mr-1" /> Functions</div>
                <div className="space-y-1">
                  {functions.map((s: SymbolMetadata, i: number) => (
                    <div key={i} className="text-sm text-green-300 truncate cursor-pointer hover:text-green-100 hover:underline flex items-center" onClick={() => onSymbolClick(s.filePath)}>
                      <ArrowRight className="w-3 h-3 mr-1 opacity-50" /> {s.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {imports.length > 0 && (
              <div>
                <div className="text-[10px] uppercase text-gray-500 mb-2 flex items-center"><Hash className="w-3 h-3 mr-1" /> Imports</div>
                <div className="space-y-1">
                  {imports.map((s: SymbolMetadata, i: number) => (
                    <div key={i} className="text-xs text-gray-400 truncate" title={s.name}>
                      {s.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {safeSymbols.length === 0 && (
              <div className="text-xs text-gray-600 italic">No meaningful symbols detected.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
