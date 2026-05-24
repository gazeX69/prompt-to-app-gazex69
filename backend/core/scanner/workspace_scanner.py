import os
import json
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB safe boundary

def get_workspaces_root() -> Path:
    # backend/core/scanner/workspace_scanner.py -> backend/core/scanner -> backend/core -> backend -> project_root -> workspaces
    return Path(__file__).resolve().parent.parent.parent.parent / "workspaces"

def get_run_dir(workspace_path: Path, run_id: Optional[str] = None) -> Optional[Path]:
    if run_id:
        target_path = workspace_path / run_id
        if target_path.exists() and target_path.is_dir():
            return target_path
        return None

    latest_path = workspace_path / "latest"
    if latest_path.exists() and latest_path.is_dir():
        return latest_path
    
    # fallback to sorting run_* dirs
    try:
        run_dirs = [d for d in workspace_path.iterdir() if d.is_dir() and d.name.startswith("run_")]
        if not run_dirs:
            return None
        # Sort by mtime
        run_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return run_dirs[0]
    except Exception:
        return None

def scan_workspaces() -> List[Dict[str, Any]]:
    root = get_workspaces_root()
    if not root.exists():
        return []
        
    workspaces = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
            
        latest_run = get_run_dir(d)
        run_count = len([x for x in d.iterdir() if x.is_dir() and x.name.startswith("run_")])
        
        stat = d.stat()
        created_at = int(stat.st_ctime * 1000)
        updated_at = int(stat.st_mtime * 1000)
        
        # basic inference for ecosystem
        ecosystem = "unknown"
        if "react" in d.name.lower(): ecosystem = "react-vite-ts"
        elif "php" in d.name.lower(): ecosystem = "php-basic"
        elif "laravel" in d.name.lower(): ecosystem = "laravel"
        
        ws = {
            "id": d.name,
            "name": d.name,
            "pathLabel": str(d.resolve()),
            "ecosystem": ecosystem,
            "createdAt": created_at,
            "updatedAt": updated_at,
            "runCount": run_count,
            "runtimeHealth": "offline"
        }
        workspaces.append(ws)
    return workspaces
    
def get_workspace_runs(workspace_id: str) -> List[Dict[str, Any]]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return []
        
    runs = []
    for d in ws_path.iterdir():
        if not d.is_dir() or not d.name.startswith("run_"):
            continue
        stat = d.stat()
        
        # Check artifacts
        orch_dir = d / ".orchestration"
        has_artifacts = orch_dir.exists() and orch_dir.is_dir()
        artifact_count = 0
        
        top_score = None
        seq_score = None
        cost_summary = None
        
        if has_artifacts:
            # naive count
            for _r, _d, _f in os.walk(orch_dir):
                artifact_count += len([f for f in _f if f.endswith(".json")])
                
            # Attempt to read alignment for top score
            top_path = orch_dir / "topology_alignment.json"
            if top_path.exists():
                try:
                    data = json.loads(top_path.read_text("utf-8"))
                    top_score = data.get("topology_alignment_score")
                except:
                    pass
                    
            # Attempt to read sequencing validation
            seq_path = orch_dir / "sequencing_validation.json"
            if seq_path.exists():
                try:
                    data = json.loads(seq_path.read_text("utf-8"))
                    seq_score = data.get("sequence_stability_score")
                except:
                    pass
                    
            # Attempt to read cost metrics
            cost_path = orch_dir / "cost_metrics.json"
            if cost_path.exists():
                try:
                    cost_summary = json.loads(cost_path.read_text("utf-8"))
                except:
                    pass

        runs.append({
            "id": d.name,
            "run_id": d.name,
            "path": str(d.resolve()),
            "prompt": "Historical run",
            "status": "success",
            "createdAt": int(stat.st_ctime * 1000),
            "updatedAt": int(stat.st_mtime * 1000),
            "startedAt": int(stat.st_ctime * 1000),
            "durationMs": 0,
            "ecosystem": "unknown",
            "hasArtifacts": has_artifacts,
            "artifactCount": artifact_count,
            "topologyScore": top_score,
            "sequencingScore": seq_score,
            "costSummary": cost_summary
        })
    return sorted(runs, key=lambda x: x["startedAt"], reverse=True)
    
def get_workspace_tree(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return {"tree": [], "ecosystem": "unknown", "totalFiles": 0}
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return {"tree": [], "ecosystem": "unknown", "totalFiles": 0}
        
    excluded = {"node_modules", "dist", "build", "vendor", "coverage", ".git", "__pycache__", ".next"}
    
    total_files = 0
    def _scan(path: Path) -> List[Dict[str, Any]]:
        nonlocal total_files
        nodes = []
        try:
            for item in path.iterdir():
                if item.name in excluded:
                    continue
                if item.is_dir():
                    children = _scan(item)
                    nodes.append({
                        "name": item.name,
                        "path": str(item.relative_to(latest_run)).replace("\\", "/"),
                        "type": "directory",
                        "children": children
                    })
                else:
                    stat = item.stat()
                    if stat.st_size > MAX_FILE_SIZE:
                        continue # Skip huge files
                        
                    if item.suffix in {'.exe', '.dll', '.png', '.jpg', '.mp4', '.zip', '.pyc', '.o', '.class'}:
                        continue
                    total_files += 1
                    
                    is_entrypoint = item.name in {"main.tsx", "App.tsx", "index.php", "index.js", "server.js", "main.py"}
                    heat = "low"
                    if item.name in {"App.tsx", "index.php", "routes.ts"}: heat = "high"
                    
                    nodes.append({
                        "name": item.name,
                        "path": str(item.relative_to(latest_run)).replace("\\", "/"),
                        "type": "file",
                        "isEntrypoint": is_entrypoint,
                        "mutationHeat": heat,
                        "referencedByCount": 0
                    })
        except Exception:
            pass
        return sorted(nodes, key=lambda x: (x["type"] != "directory", x["name"]))
        
    tree = _scan(latest_run)
    return {
        "tree": tree,
        "ecosystem": "unknown",
        "totalFiles": total_files
    }
    
def get_workspace_artifacts(workspace_id: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return []
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return []
        
    orch_dir = latest_run / ".orchestration"
    if not orch_dir.exists():
        return []
        
    artifacts = []
    
    def _find_json(path: Path):
        try:
            for item in path.iterdir():
                if item.is_dir():
                    _find_json(item)
                elif item.suffix == ".json":
                    try:
                        stat = item.stat()
                        # Safe ID encoding
                        rel_path = str(item.relative_to(orch_dir)).replace("\\", "/")
                        artifact_id = base64.urlsafe_b64encode(rel_path.encode("utf-8")).decode("utf-8")
                        
                        artifacts.append({
                            "id": artifact_id,
                            "fileName": item.name,
                            "relativePath": rel_path,
                            "sizeBytes": stat.st_size,
                            "category": "orchestration",
                            "updatedAt": int(stat.st_mtime * 1000)
                        })
                    except Exception:
                        pass
        except Exception:
            pass
            
    _find_json(orch_dir)
    return sorted(artifacts, key=lambda x: x["relativePath"])


def get_workspace_artifact_content(workspace_id: str, artifact_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return {"content": "", "truncated": False, "error": "Workspace not found"}
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return {"content": "", "truncated": False, "error": "Run not found"}
        
    orch_dir = latest_run / ".orchestration"
    
    try:
        rel_path_str = base64.urlsafe_b64decode(artifact_id.encode("utf-8")).decode("utf-8")
    except Exception:
        return {"content": "", "truncated": False, "error": "Invalid artifact ID"}
        
    # Prevent path traversal
    if ".." in rel_path_str or rel_path_str.startswith("/") or rel_path_str.startswith("\\"):
        return {"content": "", "truncated": False, "error": "Path traversal blocked"}
        
    target_path = orch_dir / rel_path_str
    
    # Final safety check
    try:
        target_resolved = target_path.resolve()
        orch_resolved = orch_dir.resolve()
        if not str(target_resolved).startswith(str(orch_resolved)):
            return {"content": "", "truncated": False, "error": "Path boundary violation"}
    except Exception:
        return {"content": "", "truncated": False, "error": "Resolution error"}
        
    if not target_path.exists() or not target_path.is_file():
        return {"content": "", "truncated": False, "error": "Artifact not found"}
        
    stat = target_path.stat()
    truncated = False
    
    try:
        if stat.st_size > MAX_FILE_SIZE:
            # Read first MAX_FILE_SIZE bytes
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_FILE_SIZE)
            truncated = True
        else:
            content = target_path.read_text(encoding="utf-8", errors="replace")
            
        return {"content": content, "truncated": truncated, "error": None}
    except Exception as e:
        return {"content": "", "truncated": False, "error": str(e)}

def get_workspace_file_content(workspace_id: str, path_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return {"content": "", "truncated": False, "error": "Workspace not found"}
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return {"content": "", "truncated": False, "error": "Run not found"}
        
    try:
        rel_path_str = base64.urlsafe_b64decode(path_id.encode("utf-8")).decode("utf-8")
    except Exception:
        return {"content": "", "truncated": False, "error": "Invalid path ID"}
        
    if ".." in rel_path_str or rel_path_str.startswith("/") or rel_path_str.startswith("\\"):
        return {"content": "", "truncated": False, "error": "Path traversal blocked"}
        
    target_path = latest_run / rel_path_str
    
    try:
        target_resolved = target_path.resolve()
        run_resolved = latest_run.resolve()
        if not str(target_resolved).startswith(str(run_resolved)):
            return {"content": "", "truncated": False, "error": "Path boundary violation"}
    except Exception:
        return {"content": "", "truncated": False, "error": "Resolution error"}
        
    if not target_path.exists() or not target_path.is_file():
        return {"content": "", "truncated": False, "error": "File not found"}
        
    stat = target_path.stat()
    if stat.st_size > MAX_FILE_SIZE:
        return {"content": "", "truncated": False, "error": "File too large"}
        
    if target_path.suffix in {'.exe', '.dll', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.zip', '.pyc', '.o', '.class', '.pdf'}:
        return {"content": "", "truncated": False, "error": "Binary files not supported"}
        
    try:
        content = target_path.read_text(encoding="utf-8", errors="replace")
        return {
            "content": content,
            "sizeBytes": stat.st_size,
            "language": target_path.suffix.lstrip('.'),
            "truncated": False,
            "error": None
        }
    except Exception as e:
        return {"content": "", "truncated": False, "error": str(e)}

import re

def extract_workspace_symbols(workspace_id: str, run_id: Optional[str] = None, path_id: Optional[str] = None) -> List[Dict[str, Any]]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return []
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return []
        
    excluded = {"node_modules", "dist", "build", "vendor", "coverage", ".git", "__pycache__", ".next"}
    symbols = []
    
    # Regex patterns (basic lightweight extraction)
    # Match imports: import { X } from 'Y' or import X from 'Y'
    import_pattern = re.compile(r'^import\s+(?:\{[^}]+\}|[^{}\s]+)', re.MULTILINE)
    # Match exports: export const X or export function X or export class X
    export_pattern = re.compile(r'^export\s+(?:default\s+)?(?:const|let|var|function|class|type|interface)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)', re.MULTILINE)
    # Match functions/classes
    func_class_pattern = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)', re.MULTILINE)
    const_func_pattern = re.compile(r'^(?:export\s+)?const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z_$][a-zA-Z0-9_$]*)\s*=>', re.MULTILINE)

    def parse_file(file_path: Path, rel_path: str):
        try:
            if file_path.stat().st_size > 1 * 1024 * 1024:
                return # Skip files > 1MB for symbol extraction
            if file_path.suffix not in {'.ts', '.tsx', '.js', '.jsx', '.py', '.php'}:
                return
                
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            
            # Extract exports
            for match in export_pattern.finditer(content):
                name = match.group(1)
                t = "component" if name[0].isupper() else "export"
                symbols.append({
                    "name": name,
                    "type": t,
                    "filePath": rel_path,
                    "exported": True,
                    "referencedCount": 0
                })
                
            # Extract funcs/classes
            for match in func_class_pattern.finditer(content):
                name = match.group(1)
                t = "component" if name[0].isupper() else "function"
                if "class " in match.group(0): t = "class"
                symbols.append({
                    "name": name,
                    "type": t,
                    "filePath": rel_path,
                    "exported": "export" in match.group(0),
                    "referencedCount": 0
                })
                
            # Extract const funcs
            for match in const_func_pattern.finditer(content):
                name = match.group(1)
                t = "component" if name[0].isupper() else "function"
                symbols.append({
                    "name": name,
                    "type": t,
                    "filePath": rel_path,
                    "exported": "export" in match.group(0),
                    "referencedCount": 0
                })
                
            # Extract imports (naive)
            for match in import_pattern.finditer(content):
                m_str = match.group(0)
                symbols.append({
                    "name": m_str[:50] + ("..." if len(m_str) > 50 else ""),
                    "type": "import",
                    "filePath": rel_path,
                    "exported": False,
                    "referencedCount": 0
                })
                
        except Exception:
            pass

    if path_id:
        try:
            rel_path_str = base64.urlsafe_b64decode(path_id.encode("utf-8")).decode("utf-8")
            if ".." not in rel_path_str and not rel_path_str.startswith("/") and not rel_path_str.startswith("\\"):
                target_file = latest_run / rel_path_str
                if target_file.exists() and target_file.is_file():
                    parse_file(target_file, rel_path_str)
        except Exception:
            pass
    else:
        def _scan_symbols(path: Path):
            try:
                for item in path.iterdir():
                    if item.name in excluded:
                        continue
                    if item.is_dir():
                        _scan_symbols(item)
                    else:
                        rel_path = str(item.relative_to(latest_run)).replace("\\", "/")
                        parse_file(item, rel_path)
            except Exception:
                pass
        _scan_symbols(latest_run)
        
    # Deduplicate naive approach (same name & type in same file)
    unique_symbols = {}
    for s in symbols:
        key = f"{s['filePath']}::{s['name']}::{s['type']}"
        if key not in unique_symbols:
            unique_symbols[key] = s
            
    return list(unique_symbols.values())

def get_workspace_references(workspace_id: str, path_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return {"error": "Workspace not found"}
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return {"error": "Run not found"}
        
    try:
        rel_path_str = base64.urlsafe_b64decode(path_id.encode("utf-8")).decode("utf-8")
    except Exception:
        return {"error": "Invalid path ID"}
        
    if ".." in rel_path_str or rel_path_str.startswith("/") or rel_path_str.startswith("\\"):
        return {"error": "Path traversal blocked"}
        
    target_path = latest_run / rel_path_str
    if not target_path.exists() or not target_path.is_file():
        return {"error": "File not found"}

    # Build full dependency graph (lightweight)
    excluded = {"node_modules", "dist", "build", "vendor", "coverage", ".git", "__pycache__", ".next"}
    import_pattern = re.compile(r'import\s+.*(?:from\s+)?[\'"]([^\'"]+)[\'"]', re.MULTILINE)
    require_pattern = re.compile(r'require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)
    
    file_imports = {} # file_path -> list of imported string paths
    
    def _scan_deps(path: Path):
        for item in path.iterdir():
            if item.name in excluded:
                continue
            if item.is_dir():
                _scan_deps(item)
            else:
                if item.suffix in {'.ts', '.tsx', '.js', '.jsx', '.py'}:
                    try:
                        content = item.read_text(encoding="utf-8", errors="ignore")
                        rel_item = str(item.relative_to(latest_run)).replace("\\", "/")
                        imports = []
                        for m in import_pattern.finditer(content):
                            imports.append(m.group(1))
                        for m in require_pattern.finditer(content):
                            imports.append(m.group(1))
                        file_imports[rel_item] = imports
                    except:
                        pass

    _scan_deps(latest_run)

    # Resolve a string import to an actual file relative path (naive heuristic)
    def resolve_import(base_file_rel: str, import_str: str) -> Optional[str]:
        if not import_str.startswith("."):
            return None # external module
        
        base_dir = Path(base_file_rel).parent
        try:
            parts = str(base_dir).replace("\\", "/").split("/")
            if parts == ["."]: parts = []
            
            for p in import_str.split("/"):
                if p == ".": continue
                elif p == "..":
                    if parts: parts.pop()
                else:
                    parts.append(p)
            
            target_base = "/".join(parts)
            
            for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"]:
                candidate = target_base + ext
                if candidate in file_imports:
                    return candidate
        except:
            pass
        return None

    # Compute dependency graph
    forward_graph = {}
    reverse_graph = {}
    
    for f in file_imports.keys():
        forward_graph[f] = []
        if f not in reverse_graph:
            reverse_graph[f] = []

    for f, imps in file_imports.items():
        for i_str in imps:
            res = resolve_import(f, i_str)
            if res:
                forward_graph[f].append(res)
                if res not in reverse_graph:
                    reverse_graph[res] = []
                reverse_graph[res].append(f)

    # For the target file
    target_rel = rel_path_str.replace("\\", "/")
    
    imported_by = list(set(reverse_graph.get(target_rel, [])))
    imports = list(set(forward_graph.get(target_rel, [])))
    
    # Compute dependency depth (bfs)
    def compute_depth(start_node, graph):
        visited = set([start_node])
        queue = [(start_node, 0)]
        max_depth = 0
        while queue:
            curr, d = queue.pop(0)
            max_depth = max(max_depth, d)
            for nbr in graph.get(curr, []):
                if nbr not in visited:
                    visited.add(nbr)
                    queue.append((nbr, d + 1))
        return max_depth
        
    depth = compute_depth(target_rel, forward_graph)
    
    ref_count = len(imported_by)
    if ref_count == 0 and len(imports) == 0:
        blast_radius = "isolated"
    elif ref_count == 0:
        blast_radius = "local"
    elif ref_count < 3:
        blast_radius = "shared"
    else:
        blast_radius = "critical"
        
    return {
        "imports": imports,
        "imported_by": imported_by,
        "dependency_depth": depth,
        "ownership_chain": ["@team-core"],
        "mutation_heat": "low",
        "blast_radius_score": blast_radius
    }

