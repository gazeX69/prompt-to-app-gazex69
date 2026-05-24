"""
Sequencing Validation Engine

Validates the reasoning quality of MutationSequenceGraph and PrerequisiteAnalyzer.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from .mutation_sequence_graph import MutationSequenceGraph, build_mutation_sequence_graph
from .prerequisite_analyzer import analyze_mutation_prerequisites

logger = logging.getLogger(__name__)

class SequencingValidator:
    """
    Validates sequencing correctness, prerequisite logic, minimality, and rollout stability.
    """
    
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.validation_dir = workspace_root / ".orchestration" / "p8" / "sequencing_validation"
        self.validation_dir.mkdir(parents=True, exist_ok=True)
        
    def validate_sequence(self, scenario_name: str, mutations: List[Any]) -> Dict[str, Any]:
        """
        Run all validations on a sequence of mutations.
        """
        # 1. Prerequisite Validation
        prereqs, prereq_graph = analyze_mutation_prerequisites(mutations)
        missing_prereqs = prereq_graph.find_missing_prerequisites()
        
        prereq_report = {
            "total_mutations": len(mutations),
            "operations_with_prerequisites": len([m for m, p in prereqs.items() if p]),
            "missing_prerequisites": len(missing_prereqs),
            "details": {
                op_id: [{"type": p.prereq_type, "target": p.target, "reason": p.reason} for p in p_list]
                for op_id, p_list in prereqs.items()
            }
        }
        
        # 2. Sequence Quality Audit & Rollout Stability Analysis
        sequence_graph = build_mutation_sequence_graph(mutations)
        sequence = sequence_graph.build_sequence()
        
        stability_score = sequence.sequence_stability_score
        stages = {k.value: v for k, v in sequence.stages.items()}
        risks = [{"type": r.risk_type.value, "severity": r.severity, "description": r.description} for r in sequence.risks]
        
        # 3. Sequence Minimality Analysis
        depths = sequence_graph.compute_sequence_depths()
        max_depth = max(depths.values()) if depths else 0
        
        # Calculate minimality (ideal depth is minimal, high depth means long chains)
        # Reducible stages can be identified if multiple stages can be merged
        parallel_groups = sequence_graph.compute_parallelizable_groups()
        
        minimality_report = {
            "max_sequence_depth": max_depth,
            "parallelizable_groups_count": len(parallel_groups),
            "compression_ratio": len(parallel_groups) / len(mutations) if mutations else 0, # Closer to 0 means highly parallelizable
            "depths": depths
        }
        
        # 4. Sequence Conflict Analysis
        cycles = sequence_graph.detect_circular_sequences()
        conflicts_report = {
            "circular_dependencies": len(cycles),
            "cycle_details": cycles,
            "mutually_dependent": [c for c in cycles if (c[1], c[0]) in cycles] # direct A<->B cycles
        }
        
        report = {
            "scenario": scenario_name,
            "prerequisite_validation": prereq_report,
            "quality_audit": {
                "stability_score": stability_score,
                "stages": stages,
                "risks": risks,
                "mutations_ordered": [n.operation_id for n in sequence.operations]
            },
            "minimality_analysis": minimality_report,
            "conflict_analysis": conflicts_report
        }
        
        self._persist_report(scenario_name, report)
        return report
        
    def _persist_report(self, scenario_name: str, report: Dict[str, Any]):
        """Persist validation report to disk."""
        out_file = self.validation_dir / f"{scenario_name}_validation.json"
        with open(out_file, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Persisted validation report to {out_file}")

