"""
Mutation Sequencing Module

Provides safe mutation ordering cognition (DRY-RUN ONLY).

Components:
- MutationSequenceGraph: Topological ordering and sequencing
- PrerequisiteAnalyzer: Identifies required mutations
- SequencingRiskAnalysis: Evaluates ordering risks
- SequenceStabilityScoring: Rates sequence safety

All analysis is deterministic and heuristic-based.
No mutations are applied.
"""

from .mutation_sequence_graph import (
    MutationSequenceGraph,
    MutationSequenceNode,
    MutationSequence,
    MutationStage,
    SequencingRisk,
    SequencingRiskType,
    PrerequisiteConstraint,
    build_mutation_sequence_graph,
)

from .prerequisite_analyzer import (
    PrerequisiteAnalyzer,
    PrerequisiteGraph,
    Prerequisite,
    PrerequisiteType,
    analyze_mutation_prerequisites,
)

__all__ = [
    'MutationSequenceGraph',
    'MutationSequenceNode',
    'MutationSequence',
    'MutationStage',
    'SequencingRisk',
    'SequencingRiskType',
    'PrerequisiteConstraint',
    'build_mutation_sequence_graph',
    'PrerequisiteAnalyzer',
    'PrerequisiteGraph',
    'Prerequisite',
    'PrerequisiteType',
    'analyze_mutation_prerequisites',
]

