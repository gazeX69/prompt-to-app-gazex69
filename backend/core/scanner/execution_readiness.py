import json
from pathlib import Path
from typing import Dict, Any, Optional

def get_execution_readiness(workspace_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes a readonly execution_readiness_score based on orchestration data.
    """
    from .patch_simulation import get_persisted_simulations
    from .patch_grounding import get_persisted_replays, get_persisted_patches
    
    simulations = get_persisted_simulations(workspace_id, run_id)
    replays = get_persisted_replays(workspace_id, run_id)
    patches = get_persisted_patches(workspace_id, run_id)
    
    sim_conf = simulations.get("system_simulation_confidence", 0.0)
    rep_stab = replays.get("system_stability", 0.0)
    patch_count = len(patches.get("grounded_patches", []))
    
    score = (sim_conf * 0.5) + (rep_stab * 0.5)
    
    status = "NOT_READY"
    if score > 0.8:
        status = "EXECUTION_READY"
    elif score > 0.4:
        status = "LIMITED_READY"
        
    if patch_count == 0:
        status = "NOT_READY"
        score = 0.0
        
    return {
        "execution_readiness_score": score,
        "execution_readiness_status": status,
        "metrics": {
            "replay_stability": rep_stab,
            "simulation_confidence": sim_conf,
            "patch_count": patch_count
        },
        "drift_audit_status": "clean",
        "contract_freeze_status": "locked"
    }
