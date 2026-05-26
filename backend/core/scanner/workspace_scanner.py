import os
import json
import base64
import datetime
import re
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.core.scanner.run_manifest import get_active_successful_run_id, read_run_manifest

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB safe boundary
PROJECT_METADATA_FILE = ".ai-agent-project.json"
TRASH_ROOT_NAME = ".trash"
SAFE_COPY_EXCLUDES = {
    "node_modules",
    "dist",
    "build",
    ".orchestration",
    ".cache",
    ".turbo",
    ".vite",
    "__pycache__",
    ".pytest_cache",
    "coverage",
}

EDIT_BLOCKED_SEGMENTS = {
    "node_modules",
    "dist",
    "build",
    ".git",
    ".trash",
    ".orchestration",
    ".cache",
    ".turbo",
    ".vite",
    "__pycache__",
    ".pytest_cache",
    "coverage",
}

TEXT_EDIT_BLOCKED_SUFFIXES = {
    ".exe", ".dll", ".png", ".jpg", ".jpeg", ".gif", ".mp4",
    ".zip", ".pyc", ".o", ".class", ".pdf", ".ico", ".webp",
}

def get_workspaces_root() -> Path:
    # backend/core/scanner/workspace_scanner.py -> backend/core/scanner -> backend/core -> backend -> project_root -> workspaces
    return Path(__file__).resolve().parent.parent.parent.parent / "workspaces"

def _now_ms() -> int:
    return int(time.time() * 1000)

def _iso_to_ms(value: Any) -> Optional[int]:
    if not isinstance(value, str) or not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return int(datetime.datetime.fromisoformat(normalized).timestamp() * 1000)
    except Exception:
        return None

def _slugify_project_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-_")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    if not cleaned:
        raise ValueError("Project name must include at least one letter or number")
    return cleaned[:64]

def _validate_project_name(name: str) -> str:
    normalized = " ".join((name or "").strip().split())
    if len(normalized) < 2:
        raise ValueError("Project name must be at least 2 characters")
    if len(normalized) > 80:
        raise ValueError("Project name must be 80 characters or fewer")
    if any(token in normalized for token in ("..", "/", "\\")):
        raise ValueError("Project name cannot contain path separators")
    return normalized

def _encode_path_id(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/")
    return base64.urlsafe_b64encode(normalized.encode("utf-8")).decode("utf-8")

def _decode_path_id(path_id: str) -> str:
    try:
        padded = path_id + ("=" * (-len(path_id) % 4))
        rel_path = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    except Exception as exc:
        raise ValueError("Invalid path ID") from exc
    return rel_path.replace("\\", "/")

def _is_unsafe_relative_path(rel_path: str) -> bool:
    return (
        ".." in rel_path
        or rel_path.startswith("/")
        or rel_path.startswith("\\")
        or Path(rel_path).is_absolute()
    )

def _ensure_workspace_root() -> Path:
    root = get_workspaces_root()
    root.mkdir(parents=True, exist_ok=True)
    return root

def _resolve_workspace_path(workspace_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", workspace_id or ""):
        raise ValueError("Invalid workspace id")
    root = _ensure_workspace_root().resolve()
    path = (root / workspace_id).resolve()
    if path.parent != root:
        raise ValueError("Workspace path escapes workspace root")
    return path

def _unique_workspace_id(name: str) -> str:
    root = _ensure_workspace_root()
    base = _slugify_project_name(name)
    candidate = base
    suffix = 2
    while (root / candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate

def _metadata_path(workspace_path: Path) -> Path:
    return workspace_path / PROJECT_METADATA_FILE

def _read_project_metadata(workspace_path: Path) -> Dict[str, Any]:
    path = _metadata_path(workspace_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _write_project_metadata(workspace_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    _metadata_path(workspace_path).write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata

def _workspace_to_project(workspace_path: Path, runtime_status: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stat = workspace_path.stat()
    metadata = _read_project_metadata(workspace_path)
    created_at = int(metadata.get("created_at") or metadata.get("createdAt") or stat.st_ctime * 1000)
    updated_at = int(metadata.get("updated_at") or metadata.get("updatedAt") or stat.st_mtime * 1000)
    name = metadata.get("name") or workspace_path.name
    ecosystem = metadata.get("ecosystem") or "unknown"
    run_count = len([x for x in workspace_path.iterdir() if x.is_dir() and x.name.startswith("run_")])
    runtime_state = (runtime_status or {}).get("status") or "unknown"
    if runtime_state == "running":
        project_status = "running"
        runtime_health = "healthy"
    elif runtime_state == "failed":
        project_status = "failed"
        runtime_health = "degraded"
    elif runtime_state == "stopped":
        project_status = "stopped"
        runtime_health = "offline"
    else:
        project_status = "ready" if workspace_path.exists() else "unknown"
        runtime_health = "offline"

    path_label = str(workspace_path.resolve())
    return {
        "id": workspace_path.name,
        "name": name,
        "path": path_label,
        "pathLabel": path_label,
        "ecosystem": ecosystem,
        "created_at": created_at,
        "updated_at": updated_at,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "runCount": run_count,
        "status": project_status,
        "runtime_status": runtime_status or {"status": "unknown"},
        "runtimeHealth": runtime_health,
        "is_archived": bool(metadata.get("is_archived", False)),
    }

def get_run_dir(workspace_path: Path, run_id: Optional[str] = None) -> Optional[Path]:
    if run_id:
        target_path = workspace_path / run_id
        if target_path.exists() and target_path.is_dir():
            return target_path
        return None

    active_run_id = get_active_successful_run_id(workspace_path.name)
    if active_run_id:
        active_path = workspace_path / active_run_id
        if active_path.exists() and active_path.is_dir() and _looks_like_source_root(active_path):
            return active_path

    latest_path = workspace_path / "latest"
    if latest_path.exists() and latest_path.is_dir() and _looks_like_source_root(latest_path):
        return latest_path

    try:
        run_dirs = [
            d for d in workspace_path.iterdir()
            if d.is_dir()
            and d.name.startswith("run_")
            and _looks_like_source_root(d)
        ]
        if not run_dirs:
            return None

        run_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return run_dirs[0]
    except Exception:
        return None

def _looks_like_source_root(path: Path) -> bool:
    return (
        (path / "package.json").is_file()
        or (path / "index.html").is_file()
        or (path / "index.php").is_file()
        or (path / "vite.config.ts").is_file()
        or (path / "vite.config.js").is_file()
        or (path / "src").is_dir()
    )


def get_latest_run_id(workspace_id: str) -> Optional[str]:
    workspace_path = _resolve_workspace_path(workspace_id)
    if not workspace_path.exists() or not workspace_path.is_dir():
        return None

    active_run_id = get_active_successful_run_id(workspace_id)
    if active_run_id and (workspace_path / active_run_id).is_dir():
        return active_run_id

    latest_path = workspace_path / "latest"
    if latest_path.exists() and latest_path.is_dir():
        return latest_path.name

    run_dir = get_run_dir(workspace_path)
    return run_dir.name if run_dir else None

def scan_workspaces() -> List[Dict[str, Any]]:
    root = get_workspaces_root()
    if not root.exists():
        return []
        
    workspaces = []
    for d in root.iterdir():
        if not d.is_dir() or d.name == TRASH_ROOT_NAME or d.name.startswith("."):
            continue
        metadata = _read_project_metadata(d)
        if metadata.get("is_archived"):
            continue
        workspaces.append(_workspace_to_project(d))
    return sorted(workspaces, key=lambda x: x["updatedAt"], reverse=True)

def create_workspace_project(name: str, template: Optional[str] = None) -> Dict[str, Any]:
    display_name = _validate_project_name(name)
    workspace_id = _unique_workspace_id(display_name)
    workspace_path = _resolve_workspace_path(workspace_id)
    workspace_path.mkdir(parents=False, exist_ok=False)
    now = _now_ms()
    metadata = {
        "id": workspace_id,
        "name": display_name,
        "ecosystem": template or "blank",
        "created_at": now,
        "updated_at": now,
        "is_archived": False,
    }
    _write_project_metadata(workspace_path, metadata)
    return _workspace_to_project(workspace_path)

def update_workspace_project(workspace_id: str, name: str) -> Dict[str, Any]:
    display_name = _validate_project_name(name)
    workspace_path = _resolve_workspace_path(workspace_id)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise FileNotFoundError("Workspace not found")
    metadata = _read_project_metadata(workspace_path)
    metadata.update({
        "id": workspace_id,
        "name": display_name,
        "updated_at": _now_ms(),
        "is_archived": bool(metadata.get("is_archived", False)),
    })
    _write_project_metadata(workspace_path, metadata)
    return _workspace_to_project(workspace_path)

def duplicate_workspace_project(workspace_id: str, name: Optional[str] = None) -> Dict[str, Any]:
    source_path = _resolve_workspace_path(workspace_id)
    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError("Workspace not found")
    source_metadata = _read_project_metadata(source_path)
    display_name = _validate_project_name(name or f"{source_metadata.get('name') or workspace_id} Copy")
    target_id = _unique_workspace_id(display_name)
    target_path = _resolve_workspace_path(target_id)

    def ignore_transient(_dir: str, names: List[str]) -> set[str]:
        return {item for item in names if item in SAFE_COPY_EXCLUDES or item.endswith(".log")}

    shutil.copytree(source_path, target_path, ignore=ignore_transient)
    now = _now_ms()
    metadata = {
        **source_metadata,
        "id": target_id,
        "name": display_name,
        "created_at": now,
        "updated_at": now,
        "is_archived": False,
    }
    _write_project_metadata(target_path, metadata)
    return _workspace_to_project(target_path)

def archive_workspace_project(workspace_id: str) -> Dict[str, Any]:
    workspace_path = _resolve_workspace_path(workspace_id)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise FileNotFoundError("Workspace not found")
    metadata = _read_project_metadata(workspace_path)
    metadata.update({
        "id": workspace_id,
        "name": metadata.get("name") or workspace_id,
        "updated_at": _now_ms(),
        "is_archived": True,
    })
    _write_project_metadata(workspace_path, metadata)

    trash_root = (_ensure_workspace_root() / TRASH_ROOT_NAME / "projects").resolve()
    workspace_root = _ensure_workspace_root().resolve()
    if not str(trash_root).startswith(str(workspace_root)):
        raise ValueError("Trash path escapes workspace root")
    trash_root.mkdir(parents=True, exist_ok=True)
    target = trash_root / f"{workspace_id}_{int(time.time())}"
    if target.exists():
        target = trash_root / f"{workspace_id}_{int(time.time())}_{os.getpid()}"
    shutil.move(str(workspace_path), str(target))
    return {
        "id": workspace_id,
        "name": metadata.get("name") or workspace_id,
        "path": str(target.resolve()),
        "pathLabel": str(target.resolve()),
        "status": "archived",
        "is_archived": True,
        "runtime_status": {"status": "stopped"},
    }
    
def get_workspace_runs(workspace_id: str) -> List[Dict[str, Any]]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return []
        
    runs = []
    for d in ws_path.iterdir():
        if not d.is_dir() or not d.name.startswith("run_"):
            continue
        stat = d.stat()
        manifest = read_run_manifest(workspace_id, d.name) or {}
        manifest_status = manifest.get("status") or "success"
        manifest_prompt = manifest.get("prompt") or "Historical run"
        manifest_created = _iso_to_ms(manifest.get("created_at")) if manifest else None
        manifest_updated = _iso_to_ms(manifest.get("updated_at")) if manifest else None
        
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
            "prompt": manifest_prompt,
            "status": manifest_status,
            "active": bool(manifest.get("active")),
            "createdAt": manifest_created or int(stat.st_ctime * 1000),
            "updatedAt": manifest_updated or int(stat.st_mtime * 1000),
            "startedAt": manifest_created or int(stat.st_ctime * 1000),
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
                    rel_path = str(item.relative_to(latest_run)).replace("\\", "/")
                    children = _scan(item)
                    nodes.append({
                        "name": item.name,
                        "path": rel_path,
                        "pathId": _encode_path_id(rel_path),
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
                    rel_path = str(item.relative_to(latest_run)).replace("\\", "/")
                    
                    nodes.append({
                        "name": item.name,
                        "path": rel_path,
                        "pathId": _encode_path_id(rel_path),
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
        rel_path_str = _decode_path_id(path_id)
    except ValueError:
        return {"content": "", "truncated": False, "error": "Invalid path ID"}
        
    if _is_unsafe_relative_path(rel_path_str):
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

def save_workspace_file_content(
    workspace_id: str,
    path_id: str,
    content: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return {"ok": False, "error": "Workspace not found"}

    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return {"ok": False, "error": "Run not found"}

    try:
        rel_path_str = _decode_path_id(path_id)
    except ValueError:
        return {"ok": False, "error": "Invalid path ID"}

    if _is_unsafe_relative_path(rel_path_str):
        return {"ok": False, "error": "Path traversal blocked"}

    rel_parts = Path(rel_path_str).parts
    if any(part in EDIT_BLOCKED_SEGMENTS for part in rel_parts):
        return {"ok": False, "error": "This path is not editable"}

    target_path = latest_run / rel_path_str

    try:
        target_resolved = target_path.resolve()
        run_resolved = latest_run.resolve()
        target_resolved.relative_to(run_resolved)
    except ValueError:
        return {"ok": False, "error": "Path boundary violation"}
    except Exception:
        return {"ok": False, "error": "Resolution error"}

    if not target_path.exists() or not target_path.is_file():
        return {"ok": False, "error": "File not found"}

    if target_path.suffix.lower() in TEXT_EDIT_BLOCKED_SUFFIXES:
        return {"ok": False, "error": "Binary files are not editable"}

    try:
        existing_head = target_path.read_bytes()[:4096]
        if b"\0" in existing_head:
            return {"ok": False, "error": "Binary files are not editable"}
    except Exception as exc:
        return {"ok": False, "error": f"Could not inspect file: {exc}"}

    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        return {"ok": False, "error": "File too large"}

    try:
        target_path.write_text(content, encoding="utf-8", newline="")
        stat = target_path.stat()
        normalized_path = rel_path_str.replace("\\", "/")
        return {
            "ok": True,
            "path": normalized_path,
            "pathId": _encode_path_id(normalized_path),
            "sizeBytes": stat.st_size,
            "language": target_path.suffix.lstrip("."),
            "updatedAt": int(stat.st_mtime * 1000),
            "error": None,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

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
            rel_path_str = _decode_path_id(path_id)
            if not _is_unsafe_relative_path(rel_path_str):
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
        rel_path_str = _decode_path_id(path_id)
    except ValueError:
        return {"error": "Invalid path ID"}
        
    if _is_unsafe_relative_path(rel_path_str):
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
