"""
Mutation Sequence Graph

Builds safe mutation ordering cognition.

Tracks:
- Prerequisite mutations
- Dependent mutations
- Ordering constraints
- Staging groups
- Safe rollout chains

DRY-RUN ONLY — no mutations applied.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class MutationStage(str, Enum):
    """Stages for safe rollout ordering."""
    FOUNDATION = "foundation"      # Types, config, constants
    TYPE_DEFINITIONS = "types"     # TypeScript interfaces, types
    PROVIDER = "provider"           # DI, context providers, factories
    COMPONENT = "component"         # UI components, features
    INTEGRATION = "integration"     # Routing, hook integration, testing


class SequencingRiskType(str, Enum):
    """Types of sequencing risks."""
    UNSAFE_ORDER = "unsafe_order"                   # Mutations in wrong order
    MISSING_PREREQUISITE = "missing_prerequisite"   # Required mutation missing
    CIRCULAR_SEQUENCE = "circular_sequence"         # Circular dependency in sequence
    INTEGRATION_ORDER = "integration_order"         # Integration point out of order
    DEPENDENCY_CHAIN_BREAK = "chain_break"          # Dependency chain interrupted


@dataclass
class PrerequisiteConstraint:
    """Represents a prerequisite for a mutation."""
    operation_id: str                    # ID of operation that must come first
    constraint_type: str                 # 'import', 'provider', 'type', 'route', 'symbol'
    reason: str                          # Why this prerequisite is required
    target_symbol: Optional[str] = None  # Symbol that must be defined


@dataclass
class MutationSequenceNode:
    """A mutation in the sequence graph."""
    operation_id: str
    target_file: str
    stage: MutationStage
    prerequisites: List[PrerequisiteConstraint] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)  # operation_ids that depend on this
    sequence_depth: int = 0              # Depth in dependency chain (0 = no prereqs)
    is_blocking: bool = False            # Blocks other mutations if broken


@dataclass
class SequencingRisk:
    """Identified risk in mutation sequence."""
    risk_type: SequencingRiskType
    severity: int                       # 1-5 scale
    affected_operations: List[str]
    description: str
    mitigation: Optional[str] = None


@dataclass
class MutationSequence:
    """Safe ordering for a set of mutations."""
    sequence_id: str
    operations: List[MutationSequenceNode]
    stages: Dict[MutationStage, List[str]]  # stage -> operation_ids
    risks: List[SequencingRisk] = field(default_factory=list)
    sequence_stability_score: float = 0.0  # 1.0-10.0 scale
    can_be_parallelized: List[Set[str]] = field(default_factory=list)  # Groups that can run in parallel


class MutationSequenceGraph:
    """
    Builds and analyzes mutation sequences.
    
    Tracks prerequisite relationships and safe ordering.
    """

    def __init__(self):
        self.nodes: Dict[str, MutationSequenceNode] = {}
        self.edges: Dict[str, Set[str]] = {}  # operation_id -> [dependent_ids]
        self.reverse_edges: Dict[str, Set[str]] = {}  # operation_id -> [prerequisite_ids]

    def add_node(self, node: MutationSequenceNode) -> None:
        """Add a mutation to the graph."""
        self.nodes[node.operation_id] = node
        if node.operation_id not in self.edges:
            self.edges[node.operation_id] = set()
        if node.operation_id not in self.reverse_edges:
            self.reverse_edges[node.operation_id] = set()

    def add_prerequisite(
        self,
        operation_id: str,
        prerequisite_id: str,
        constraint: PrerequisiteConstraint
    ) -> None:
        """Mark that operation_id requires prerequisite_id."""
        if operation_id not in self.nodes:
            logger.warning(f"Operation {operation_id} not in graph")
            return
        
        self.nodes[operation_id].prerequisites.append(constraint)
        self.edges[prerequisite_id].add(operation_id)
        self.reverse_edges[operation_id].add(prerequisite_id)

    def compute_sequence_depths(self) -> Dict[str, int]:
        """Compute depth of each operation in dependency chain."""
        depths = {}
        visited = set()
        
        def dfs(op_id: str) -> int:
            if op_id in visited:
                return depths.get(op_id, 0)
            
            visited.add(op_id)
            
            # Get max depth of all prerequisites
            prereq_depths = [
                dfs(prereq_id) for prereq_id in self.reverse_edges.get(op_id, [])
            ]
            
            depth = (max(prereq_depths) + 1) if prereq_depths else 0
            depths[op_id] = depth
            self.nodes[op_id].sequence_depth = depth
            
            return depth
        
        for op_id in self.nodes.keys():
            dfs(op_id)
        
        return depths

    def detect_circular_sequences(self) -> List[Tuple[str, str]]:
        """Detect circular dependencies in mutation sequence."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for dependent in self.edges.get(node, []):
                if dependent not in visited:
                    dfs(dependent, path)
                elif dependent in rec_stack:
                    # Found cycle
                    cycle_start = path.index(dependent)
                    for i in range(cycle_start, len(path)):
                        cycles.append((path[i], dependent))
            
            rec_stack.remove(node)
        
        for node_id in self.nodes.keys():
            if node_id not in visited:
                dfs(node_id, [])
        
        return cycles

    def topological_sort(self) -> List[str]:
        """Return topologically sorted operation IDs."""
        depths = self.compute_sequence_depths()
        sorted_ops = sorted(self.nodes.keys(), key=lambda x: depths.get(x, 0))
        return sorted_ops

    def get_staging_groups(self) -> Dict[MutationStage, List[str]]:
        """Group operations by stage."""
        stages = {}
        for op_id, node in self.nodes.items():
            if node.stage not in stages:
                stages[node.stage] = []
            stages[node.stage].append(op_id)
        
        return stages

    def compute_parallelizable_groups(self) -> List[Set[str]]:
        """
        Compute groups of mutations that can run in parallel.
        
        Two mutations can run in parallel if neither depends on the other.
        """
        groups = []
        remaining = set(self.nodes.keys())
        
        while remaining:
            # Find all nodes with no remaining prerequisites
            ready = set()
            for op_id in remaining:
                prereqs = self.reverse_edges.get(op_id, set())
                if not (prereqs & remaining):  # No prerequisites in remaining
                    ready.add(op_id)
            
            if not ready:
                # Circular dependency or all remaining are blocked
                ready = {remaining.pop()}
            
            groups.append(ready)
            remaining -= ready
        
        return groups

    def build_sequence(self) -> MutationSequence:
        """Build safe mutation sequence."""
        sequence_id = f"seq_{len(self.nodes)}_ops"
        
        # Compute depths
        depths = self.compute_sequence_depths()
        
        # Detect cycles
        cycles = self.detect_circular_sequences()
        
        # Get stage groups
        stages = self.get_staging_groups()
        
        # Get parallelizable groups
        parallel_groups = self.compute_parallelizable_groups()
        
        # Analyze risks
        risks = self._analyze_sequence_risks(cycles)
        
        # Compute stability score
        stability = self._compute_stability_score(depths, cycles, stages)
        
        # Build sorted node list
        sorted_op_ids = self.topological_sort()
        sorted_nodes = [self.nodes[op_id] for op_id in sorted_op_ids]
        
        return MutationSequence(
            sequence_id=sequence_id,
            operations=sorted_nodes,
            stages=stages,
            risks=risks,
            sequence_stability_score=stability,
            can_be_parallelized=parallel_groups,
        )

    def _analyze_sequence_risks(self, cycles: List[Tuple[str, str]]) -> List[SequencingRisk]:
        """Analyze risks in the mutation sequence."""
        risks = []
        
        # Circular sequence risk
        if cycles:
            affected = set()
            for a, b in cycles:
                affected.add(a)
                affected.add(b)
            
            risks.append(SequencingRisk(
                risk_type=SequencingRiskType.CIRCULAR_SEQUENCE,
                severity=5,
                affected_operations=list(affected),
                description=f"Circular dependency detected: {len(cycles)} cycles",
                mitigation="Reorder mutations to break cycles"
            ))
        
        # Missing prerequisite risk
        for op_id, node in self.nodes.items():
            for prereq in node.prerequisites:
                if prereq.operation_id not in self.nodes:
                    risks.append(SequencingRisk(
                        risk_type=SequencingRiskType.MISSING_PREREQUISITE,
                        severity=4,
                        affected_operations=[op_id],
                        description=f"Prerequisite {prereq.operation_id} missing from sequence",
                        mitigation="Add required prerequisite operation"
                    ))
        
        # Integration order risk (integration stage depending on component stage)
        integration_ops = [
            op_id for op_id, node in self.nodes.items()
            if node.stage == MutationStage.INTEGRATION
        ]
        
        for int_op in integration_ops:
            node = self.nodes[int_op]
            unmet_prereqs = []
            for prereq in node.prerequisites:
                if prereq.operation_id in self.nodes:
                    prereq_node = self.nodes[prereq.operation_id]
                    if prereq_node.stage == MutationStage.FOUNDATION:
                        unmet_prereqs.append(prereq.operation_id)
            
            if unmet_prereqs:
                risks.append(SequencingRisk(
                    risk_type=SequencingRiskType.INTEGRATION_ORDER,
                    severity=3,
                    affected_operations=[int_op] + unmet_prereqs,
                    description="Integration stage depends on foundation stage",
                    mitigation="Ensure foundation stage completes first"
                ))
        
        # Dependency chain break risk (long chains)
        depths = self.compute_sequence_depths()
        for op_id, depth in depths.items():
            if depth > 5:
                risks.append(SequencingRisk(
                    risk_type=SequencingRiskType.DEPENDENCY_CHAIN_BREAK,
                    severity=depth - 3,  # Higher severity for deeper chains
                    affected_operations=[op_id],
                    description=f"Deep dependency chain (depth {depth})",
                    mitigation="Break into smaller sequences"
                ))
        
        return risks

    def _compute_stability_score(
        self,
        depths: Dict[str, int],
        cycles: List[Tuple[str, str]],
        stages: Dict[MutationStage, List[str]]
    ) -> float:
        """
        Compute sequence stability score (1.0-10.0).
        
        Rewards:
        - Short safe chains
        - Isolated rollout groups
        - Minimal prerequisite depth
        
        Penalizes:
        - Long mutation chains
        - Circular staging
        - Root-level bottlenecks
        """
        score = 10.0
        
        # Penalize for depth
        max_depth = max(depths.values()) if depths else 0
        score -= min(5.0, max_depth * 0.5)
        
        # Penalize for cycles
        score -= len(cycles) * 2
        
        # Penalize for stage bottlenecks
        foundation_ops = len(stages.get(MutationStage.FOUNDATION, []))
        if foundation_ops > 5:
            score -= 2.0
        
        # Reward for good stage distribution
        num_stages = len([s for s in stages.values() if s])
        if num_stages >= 3:
            score += 1.0
        
        # Ensure score in range
        score = max(1.0, min(10.0, score))
        
        return score


def build_mutation_sequence_graph(
    mutations: List[Any],  # MutationEdit from minimal_mutation
) -> MutationSequenceGraph:
    """
    Build sequence graph from a list of mutations.
    
    Args:
        mutations: List of mutation operations
    
    Returns:
        MutationSequenceGraph with ordering relationships
    """
    graph = MutationSequenceGraph()
    
    # Add nodes for each mutation
    for i, mutation in enumerate(mutations):
        node = MutationSequenceNode(
            operation_id=f"op_{i}",
            target_file=getattr(mutation, 'target_file', 'unknown'),
            stage=_infer_mutation_stage(getattr(mutation, 'target_file', '')),
        )
        graph.add_node(node)
    
    # Infer prerequisites
    for i, mutation in enumerate(mutations):
        prereqs = _infer_prerequisites(mutation, mutations)
        for prereq_idx, constraint in prereqs:
            if 0 <= prereq_idx < len(mutations):
                graph.add_prerequisite(
                    f"op_{i}",
                    f"op_{prereq_idx}",
                    constraint
                )
    
    return graph


def _infer_mutation_stage(file_path: str) -> MutationStage:
    """Infer which stage a mutation belongs to based on file path."""
    file_lower = file_path.lower()
    
    if any(p in file_lower for p in ['types', 'interfaces', 'models', 'schema']):
        return MutationStage.TYPE_DEFINITIONS
    
    if any(p in file_lower for p in ['provider', 'context', 'factory', 'service', 'injection']):
        return MutationStage.PROVIDER
    
    if any(p in file_lower for p in ['component', 'page', 'screen']):
        return MutationStage.COMPONENT
    
    if any(p in file_lower for p in ['route', 'router', 'hook', 'integration', 'index']):
        return MutationStage.INTEGRATION
    
    if any(p in file_lower for p in ['config', 'constant', 'env', 'setup']):
        return MutationStage.FOUNDATION
    
    # Default: depends on what we're doing
    return MutationStage.COMPONENT


def _infer_prerequisites(
    mutation: Any,
    all_mutations: List[Any]
) -> List[Tuple[int, PrerequisiteConstraint]]:
    """
    Infer prerequisite mutations for a given mutation.
    
    Returns list of (mutation_index, constraint) tuples.
    """
    prerequisites = []
    
    target_file = getattr(mutation, 'target_file', '')
    code = getattr(mutation, 'code_to_insert', '')
    
    # Analyze exports of all mutations to find who provides what
    provided_by = {}
    for idx, m in enumerate(all_mutations):
        m_code = getattr(m, 'code_to_insert', '')
        # Simple export heuristic
        for word in ['interface', 'type', 'const', 'function', 'class']:
            if f'export {word} ' in m_code:
                symbol = m_code.split(f'export {word} ')[1].split(' ')[0].split('(')[0].split('<')[0]
                provided_by[symbol] = idx

    # If this mutation imports or uses a symbol, check if another mutation provides it
    for symbol, idx in provided_by.items():
        if symbol in code and getattr(all_mutations[idx], 'target_file', '') != target_file:
            prerequisites.append((
                idx,
                PrerequisiteConstraint(
                    operation_id=f"op_{idx}",
                    constraint_type="symbol",
                    reason=f"Requires {symbol}",
                    target_symbol=symbol
                )
            ))
            
    return prerequisites


