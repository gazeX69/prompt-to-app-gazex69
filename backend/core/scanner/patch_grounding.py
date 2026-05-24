import re
import json
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional

# Mock core imports for paths
# We will use the same pattern as workspace_scanner.py
def _get_p6_dir(workspace_id: str, run_id: Optional[str] = None) -> Path:
    from .workspace_scanner import get_workspaces_root, get_run_dir
    ws_path = get_workspaces_root() / workspace_id
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return None
    p6_dir = latest_run / ".orchestration" / "p6"
    p6_dir.mkdir(parents=True, exist_ok=True)
    return p6_dir

def _get_p65_dir(workspace_id: str, run_id: Optional[str] = None) -> Path:
    from .workspace_scanner import get_workspaces_root, get_run_dir
    ws_path = get_workspaces_root() / workspace_id
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return None
    p65_dir = latest_run / ".orchestration" / "p65"
    p65_dir.mkdir(parents=True, exist_ok=True)
    return p65_dir

def detect_file_regions(content: str) -> List[Dict[str, Any]]:
    """
    Identifies logical regions within a file using lightweight regex parsing.
    Returns a list of regions with their start/end line numbers (1-indexed).
    """
    lines = content.split('\n')
    regions = []
    
    # Simple heuristics
    in_imports = False
    imports_start = -1
    
    for i, line in enumerate(lines):
        line_num = i + 1
        line_clean = line.strip()
        
        # Imports zone
        is_import = line_clean.startswith("import ") or line_clean.startswith("require(")
        if is_import and not in_imports:
            in_imports = True
            imports_start = line_num
        elif not is_import and line_clean != "" and in_imports:
            in_imports = False
            regions.append({
                "type": "imports_zone",
                "start_line": imports_start,
                "end_line": line_num - 1
            })
            
    # Component / Function zones
    comp_pattern = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:function|const)\s+([A-Z]\w*)')
    func_pattern = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:function|const)\s+([a-z]\w*)')
    hook_pattern = re.compile(r'^(?:export\s+)?(?:default\s+)?(?:function|const)\s+(use[A-Z]\w*)')
    
    current_zone = None
    bracket_depth = 0
    
    for i, line in enumerate(lines):
        line_num = i + 1
        
        # Start of a new block
        if bracket_depth == 0:
            hook_match = hook_pattern.search(line)
            if hook_match:
                current_zone = {"type": "hook_zone", "name": hook_match.group(1), "start_line": line_num}
                
            comp_match = comp_pattern.search(line)
            if comp_match and not current_zone:
                current_zone = {"type": "component_zone", "name": comp_match.group(1), "start_line": line_num}
                
            func_match = func_pattern.search(line)
            if func_match and not current_zone:
                current_zone = {"type": "utility_zone", "name": func_match.group(1), "start_line": line_num}
                
        # Track brackets for basic block matching
        bracket_depth += line.count('{')
        bracket_depth -= line.count('}')
        
        if bracket_depth <= 0 and current_zone and line.count('}') > 0:
            # End of block
            current_zone["end_line"] = line_num
            regions.append(current_zone)
            current_zone = None
            bracket_depth = 0 # reset
            
    # Ensure any open imports zone is closed if it hit EOF
    if in_imports:
        regions.append({
            "type": "imports_zone",
            "start_line": imports_start,
            "end_line": len(lines)
        })
        
    # Sort regions by start line
    regions.sort(key=lambda x: x["start_line"])
    return regions

def synthesize_grounded_patch(
    workspace_id: str, 
    path_id: str, 
    run_id: str, 
    patch_type: str, 
    target_content: str,
    target_symbol: Optional[str] = None,
    target_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a dry-run grounded patch with structural classification and collision cognition.
    """
    # This is a mock implementation for demonstration.
    # In a real system, it would use the AI's output and map it to the AST/regions.
    
    confidence = 0.85
    locality = "local"
    blast_radius = "low"
    
    if patch_type in ["append_import", "modify_props"]:
        confidence = 0.95
    elif patch_type == "inject_component":
        confidence = 0.70
        blast_radius = "medium"
        
    return {
        "patch_type": patch_type,
        "target_file": target_file or "unknown",
        "target_symbol": target_symbol,
        "target_region": {
            "start_line": 10,
            "end_line": 15
        },
        "grounding_context": {
            "surrounding_lines": ["// context before", "// context after"],
            "nearby_symbols": ["ExampleComponent"],
            "ownership": "@team-core"
        },
        "prerequisite_symbols": [],
        "affected_imports": [],
        "dependency_zone": "shared",
        "confidence_score": confidence,
        "locality": locality,
        "blast_radius": blast_radius,
        "collisions": [], # collision cognition
        # P6.5 Drift Extensions
        "original_line_window": "10-15",
        "grounding_hash": "hash_v1",
        "nearby_symbol_hash": "sym_hash_v1",
        "import_snapshot": ["react"],
        "replay_generation": 1
    }

def evaluate_patch_replay(patch: Dict[str, Any], current_content: str) -> Dict[str, Any]:
    """
    Evaluates a patch against current file content for drift, relocation, and replay safety.
    """
    lines = current_content.split('\n')
    
    # 1. Drift Detection & Fuzzy Recovery
    drift_state = "stable"
    stale_warning = False
    relocation_confidence = 1.0
    stability_score = 0.95
    replay_safety = "safe"
    new_region = patch.get("target_region", {"start_line": 10, "end_line": 15}).copy()
    
    # Mock fuzzy logic
    if patch.get("target_symbol") == "missing":
        replay_safety = "unsafe"
        stability_score = 0.1
        drift_state = "symbol_deleted"
        stale_warning = True
        relocation_confidence = 0.0
    elif len(lines) != 500: # mock condition to trigger drift
        drift_state = "shifted"
        stability_score = 0.75
        new_region["start_line"] += 2
        new_region["end_line"] += 2
        replay_safety = "degraded"
        relocation_confidence = 0.85
        
    # 2. Duplicate Detection
    duplicate_injection = False
    if patch["patch_type"] == "append_import" and "import { X }" in current_content:
        duplicate_injection = True
        replay_safety = "unsafe"
        stale_warning = True
        stability_score = 0.3
        
    return {
        "patch_id": patch.get("patch_id", "unknown"),
        "replay_safety": replay_safety,
        "drift_state": drift_state,
        "stale_warning": stale_warning,
        "relocated_region": new_region,
        "relocation_confidence": relocation_confidence,
        "stability_score": stability_score,
        "duplicate_injection_detected": duplicate_injection,
        "replay_generation": patch.get("replay_generation", 1) + 1
    }

def detect_collisions(patches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detects overlapping regions and duplicate insertions among pending patches.
    """
    collisions = []
    # simple overlap detection
    for i in range(len(patches)):
        for j in range(i + 1, len(patches)):
            p1 = patches[i]
            p2 = patches[j]
            
            r1 = p1.get("target_region")
            r2 = p2.get("target_region")
            
            if r1 and r2:
                # Check overlap
                if max(r1["start_line"], r2["start_line"]) <= min(r1["end_line"], r2["end_line"]):
                    collisions.append({
                        "type": "overlapping_region",
                        "patch_1": p1["patch_type"],
                        "patch_2": p2["patch_type"],
                        "lines": f"{max(r1['start_line'], r2['start_line'])}-{min(r1['end_line'], r2['end_line'])}"
                    })
    return collisions

def get_workspace_regions(workspace_id: str, path_id: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    from .workspace_scanner import get_workspaces_root, get_run_dir
    ws_path = get_workspaces_root() / workspace_id
    if not ws_path.exists():
        return []
        
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return []
        
    try:
        rel_path_str = base64.urlsafe_b64decode(path_id.encode("utf-8")).decode("utf-8")
    except Exception:
        return []
        
    target_path = latest_run / rel_path_str
    if not target_path.exists() or not target_path.is_file():
        return []

    try:
        content = target_path.read_text(encoding="utf-8", errors="ignore")
        return detect_file_regions(content)
    except:
        return []

def generate_and_persist_patches(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Simulates generating grounded patches and persisting them to .orchestration/p6/
    """
    p6_dir = _get_p6_dir(workspace_id, run_id)
    if not p6_dir:
        return {"error": "Run not found"}
        
    # Generate mock patches
    patch1 = synthesize_grounded_patch(workspace_id, "mock1", run_id, "append_import", "import { X } from 'y'", target_file="src/App.tsx")
    patch2 = synthesize_grounded_patch(workspace_id, "mock2", run_id, "inject_component", "const X = () => <div/>", target_file="src/App.tsx")
    
    patches = [patch1, patch2]
    collisions = detect_collisions(patches)
    
    data = {
        "grounded_patches": patches,
        "collision_reports": collisions,
        "confidence_scores": [p["confidence_score"] for p in patches],
        "region_maps_generated": True
    }
    
    # Persist
    (p6_dir / "patches.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    
    return data

def get_persisted_patches(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    p6_dir = _get_p6_dir(workspace_id, run_id)
    if not p6_dir:
        return {"grounded_patches": [], "collision_reports": []}
        
    patches_file = p6_dir / "patches.json"
    if patches_file.exists():
        try:
            return json.loads(patches_file.read_text(encoding="utf-8"))
        except:
            pass
            
    # Auto-generate if missing for demo purposes
    return generate_and_persist_patches(workspace_id, run_id)

def generate_and_persist_replays(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    p65_dir = _get_p65_dir(workspace_id, run_id)
    if not p65_dir:
        return {"error": "Run not found"}
        
    patches_data = get_persisted_patches(workspace_id, run_id)
    patches = patches_data.get("grounded_patches", [])
    
    mock_content = "import { Y } from 'y';\n" * 500 # triggers shifted
    
    reports = []
    for i, p in enumerate(patches):
        # Force one to be unstable for demo
        if i == 1:
            p["target_symbol"] = "missing"
            
        report = evaluate_patch_replay(p, mock_content)
        report["patch_id"] = p["patch_type"] + f"_{i}" # associate it
        reports.append(report)
        
    data = {
        "replay_reports": reports,
        "stale_patch_warnings": [r for r in reports if r["stale_warning"]],
        "system_stability": sum(r["stability_score"] for r in reports) / max(1, len(reports))
    }
    
    (p65_dir / "replays.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

def get_persisted_replays(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    p65_dir = _get_p65_dir(workspace_id, run_id)
    if not p65_dir:
        return {"replay_reports": []}
        
    replays_file = p65_dir / "replays.json"
    if replays_file.exists():
        try:
            return json.loads(replays_file.read_text(encoding="utf-8"))
        except:
            pass
            
    return generate_and_persist_replays(workspace_id, run_id)
