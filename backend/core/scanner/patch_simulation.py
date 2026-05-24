import json
from pathlib import Path
from typing import List, Dict, Any, Optional

def _get_p66_dir(workspace_id: str, run_id: Optional[str] = None) -> Path:
    from .workspace_scanner import get_workspaces_root, get_run_dir
    ws_path = get_workspaces_root() / workspace_id
    latest_run = get_run_dir(ws_path, run_id)
    if not latest_run:
        return None
    p66_dir = latest_run / ".orchestration" / "p66"
    p66_dir.mkdir(parents=True, exist_ok=True)
    return p66_dir

def run_syntax_sanity(content: str) -> Dict[str, Any]:
    """Lightweight bracket and syntax balance checks."""
    braces = 0
    brackets = 0
    parens = 0
    
    for char in content:
        if char == '{': braces += 1
        elif char == '}': braces -= 1
        elif char == '[': brackets += 1
        elif char == ']': brackets -= 1
        elif char == '(': parens += 1
        elif char == ')': parens -= 1
        
    passed = braces == 0 and brackets == 0 and parens == 0
    
    return {
        "passed": passed,
        "balance": {
            "braces": braces,
            "brackets": brackets,
            "parens": parens
        }
    }

def simulate_patch_application(
    current_content: str, 
    patch: Dict[str, Any], 
    replay_report: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Simulates applying a patch based on its replay report safety.
    """
    lines = current_content.split('\n')
    before_count = len(lines)
    
    skipped_reasons = []
    
    # 1. Guardrails
    if replay_report.get("replay_safety") == "unsafe":
        skipped_reasons.append("unsafe_replay")
    if replay_report.get("duplicate_injection_detected"):
        skipped_reasons.append("duplicate_injection")
    if replay_report.get("stability_score", 0) < 0.5:
        skipped_reasons.append("low_stability")
        
    if skipped_reasons:
        return {
            "patch_id": replay_report.get("patch_id", "unknown"),
            "status": "skipped",
            "skipped_reasons": skipped_reasons,
            "before_line_count": before_count,
            "after_line_count": before_count,
            "changed_regions": [],
            "syntax_sanity": {"passed": True, "balance": {"braces": 0, "brackets": 0, "parens": 0}},
            "simulation_confidence_score": 0.0
        }
        
    # 2. Application
    # For demonstration, we'll insert a mock payload at the relocated region start line.
    target_region = replay_report.get("relocated_region", patch.get("target_region", {"start_line": 1}))
    start_idx = max(0, target_region["start_line"] - 1)
    
    # In a real system, we'd replace the lines. Here we just inject.
    mock_payload = ["// --- SIMULATED INJECTION ---", "const SIMULATED = true;", "// -------------------------"]
    
    simulated_lines = lines[:start_idx] + mock_payload + lines[start_idx:]
    simulated_content = "\n".join(simulated_lines)
    
    # 3. Syntax Sanity
    sanity = run_syntax_sanity(simulated_content)
    
    # 4. Confidence Score
    conf = replay_report.get("relocation_confidence", 1.0) * replay_report.get("stability_score", 1.0)
    if not sanity["passed"]:
        conf *= 0.1 # heavily penalize imbalanced syntax
        
    return {
        "patch_id": replay_report.get("patch_id", "unknown"),
        "status": "applied",
        "skipped_reasons": [],
        "before_line_count": before_count,
        "after_line_count": len(simulated_lines),
        "changed_regions": [{
            "start_line": target_region["start_line"],
            "end_line": target_region["start_line"] + len(mock_payload) - 1,
            "type": "simulated_injection"
        }],
        "syntax_sanity": sanity,
        "simulation_confidence_score": conf
    }

def generate_and_persist_simulations(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    from .patch_grounding import get_persisted_patches, get_persisted_replays
    
    p66_dir = _get_p66_dir(workspace_id, run_id)
    if not p66_dir:
        return {"error": "Run not found"}
        
    patches_data = get_persisted_patches(workspace_id, run_id)
    replays_data = get_persisted_replays(workspace_id, run_id)
    
    patches = patches_data.get("grounded_patches", [])
    reports = replays_data.get("replay_reports", [])
    
    # Mock content for simulation
    mock_content = "import { Y } from 'y';\n" * 500
    
    simulations = []
    
    for i, p in enumerate(patches):
        patch_id = p["patch_type"] + f"_{i}"
        report = next((r for r in reports if r.get("patch_id") == patch_id), {})
        
        sim = simulate_patch_application(mock_content, p, report)
        simulations.append(sim)
        
    data = {
        "simulation_reports": simulations,
        "system_simulation_confidence": sum(s["simulation_confidence_score"] for s in simulations) / max(1, len(simulations))
    }
    
    (p66_dir / "simulations.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data

def get_persisted_simulations(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    p66_dir = _get_p66_dir(workspace_id, run_id)
    if not p66_dir:
        return {"simulation_reports": []}
        
    sim_file = p66_dir / "simulations.json"
    if sim_file.exists():
        try:
            return json.loads(sim_file.read_text(encoding="utf-8"))
        except:
            pass
            
    return generate_and_persist_simulations(workspace_id, run_id)
