"""
Safe patching engine for existing projects.

Provides targeted file modification without destructive overwrite.
Supports context-aware edits, targeted replacements, and architecture-aware targeting.
Includes ownership propagation and dependency-aware mutation cognition.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
import json

from backend.agent.tools import read_file, write_file, list_project_files, _safe_project_path
from backend.core.scanner.engine import scan_project, ProjectScanResult

logger = logging.getLogger(__name__)


@dataclass
class OwnershipInfo:
    """Ownership metadata for a module."""
    module_path: str
    primary_owner: Optional[str]  # inferred from path, e.g., 'auth', 'dashboard'
    ownership_chain: List[str]  # hierarchical ownership path
    is_shared: bool  # belongs to multiple owners
    shared_owners: List[str]  # if shared, list of owners


@dataclass
class MutationImpact:
    """Impact assessment for a mutation."""
    target_file: str
    affected_modules: List[str]  # modules that depend on target
    ownership_scope: List[OwnershipInfo]
    mutation_locality: int  # 1=isolated, 5=high ripple
    collision_risk: int  # 1=low, 5=high (high-dependency zones)
    estimated_cascade: int  # estimated files in cascade


@dataclass
class PatchOperation:
    relative_path: str
    old_string: str
    new_string: str
    description: str = ""


@dataclass
class PatchPlan:
    project_id: str
    operations: list[PatchOperation] = field(default_factory=list)
    scan: Optional[ProjectScanResult] = None
    target_files: list[str] = field(default_factory=list)
    impact_assessments: Dict[str, MutationImpact] = field(default_factory=dict)

    def add_replace(self, rel_path: str, old: str, new: str, desc: str = "") -> None:
        self.operations.append(PatchOperation(rel_path, old, new, desc))

    def add_file(self, rel_path: str, content: str) -> None:
        self.operations.append(PatchOperation(rel_path, "", content, "new file"))


def build_patch_plan(project_id: str) -> PatchPlan:
    """
    Build a patch plan for a project based on its architecture scan.
    Identifies target files and returns an empty plan ready for operations.
    """
    project_path = _safe_project_path(project_id)
    scan = scan_project(project_path)
    files = list_project_files(project_id)

    target_files = _select_targets(scan, files)

    return PatchPlan(
        project_id=project_id,
        scan=scan,
        target_files=target_files,
    )


def apply_patch_plan(plan: PatchPlan) -> list[str]:
    """
    Apply all operations in a patch plan.
    Returns list of modified file paths.
    """
    modified = []
    for op in plan.operations:
        try:
            if op.old_string == "" and op.new_string != "":
                write_file(plan.project_id, op.relative_path, op.new_string)
                modified.append(op.relative_path)
                logger.info("Created %s (%s)", op.relative_path, op.description or "new file")
            else:
                _apply_targeted_edit(plan.project_id, op)
                modified.append(op.relative_path)
                logger.info("Patched %s (%s)", op.relative_path, op.description or "edit")
        except Exception as e:
            logger.error("Failed to patch %s: %s", op.relative_path, e)
    return modified


def assess_mutation_impact(
    target_file: str,
    repo_map: Optional[object] = None,
    reverse_deps: Optional[Dict[str, List[str]]] = None,
) -> MutationImpact:
    """
    Assess impact of mutating a target file.
    
    Analyzes:
    - which modules depend on target
    - ownership chains of affected modules
    - mutation locality score
    - collision risk in high-dependency zones
    """
    affected_modules = reverse_deps.get(target_file, []) if reverse_deps else []
    ownership_scope = _infer_ownership_chain(target_file, affected_modules)
    
    mutation_locality = _score_mutation_locality(
        target_file, affected_modules, repo_map
    )
    collision_risk = _score_collision_risk(
        target_file, affected_modules, repo_map
    )
    
    return MutationImpact(
        target_file=target_file,
        affected_modules=affected_modules,
        ownership_scope=ownership_scope,
        mutation_locality=mutation_locality,
        collision_risk=collision_risk,
        estimated_cascade=len(affected_modules),
    )


def _infer_ownership_chain(target_file: str, affected_modules: List[str]) -> List[OwnershipInfo]:
    """Infer ownership from file paths and module structure."""
    ownerships = []
    
    # Extract primary owner from path (heuristic: first folder after src/)
    path_parts = target_file.split('/')
    primary_owner = None
    ownership_chain = []
    
    if 'src' in path_parts:
        src_idx = path_parts.index('src')
        if src_idx + 1 < len(path_parts):
            primary_owner = path_parts[src_idx + 1]
            ownership_chain = path_parts[src_idx:src_idx + 3]
    elif 'app' in path_parts:
        app_idx = path_parts.index('app')
        if app_idx + 1 < len(path_parts):
            primary_owner = path_parts[app_idx + 1]
            ownership_chain = path_parts[app_idx:app_idx + 3]
    
    # Analyze affected modules for ownership
    shared_owners = set()
    for module in affected_modules:
        module_owner = _extract_owner_from_path(module)
        if module_owner:
            shared_owners.add(module_owner)
    
    is_shared = len(shared_owners) > 1 or (primary_owner and primary_owner in shared_owners)
    
    ownerships.append(OwnershipInfo(
        module_path=target_file,
        primary_owner=primary_owner,
        ownership_chain=ownership_chain,
        is_shared=is_shared,
        shared_owners=list(shared_owners),
    ))
    
    return ownerships


def _extract_owner_from_path(module_path: str) -> Optional[str]:
    """Extract owner designation from module path."""
    path_parts = module_path.split('/')
    
    # Check for common ownership patterns
    for idx, part in enumerate(path_parts):
        if part in ['src', 'app', 'components', 'pages']:
            if idx + 1 < len(path_parts):
                candidate = path_parts[idx + 1]
                # Owner is typically a folder at feature/domain level
                if not candidate.endswith('.ts') and not candidate.endswith('.js') and not candidate.endswith('.tsx'):
                    return candidate
    
    return None


def _score_mutation_locality(
    target_file: str,
    affected_modules: List[str],
    repo_map: Optional[object] = None,
) -> int:
    """
    Score mutation locality: 1=isolated, 5=high ripple.
    
    Factors:
    - number of affected modules
    - depth of dependency chain
    - is target in core/shared areas
    """
    score = 1
    
    # Penalty: affected modules
    if len(affected_modules) > 0:
        score = min(5, 1 + len(affected_modules) // 3)
    
    # Penalty: core/shared files
    if any(part in target_file for part in ['core', 'shared', 'utils', 'constants', 'types', 'config']):
        score = min(5, score + 1)
    
    # Penalty: entrypoint or top-level
    if '/' not in target_file or target_file.count('/') <= 1:
        score = min(5, score + 1)
    
    # Bonus: isolated feature file
    if any(part in target_file for part in ['components', 'features', 'modules']):
        score = max(1, score - 1)
    
    # Check ripple depth if repo_map available
    if repo_map and hasattr(repo_map, 'dependency_ripples'):
        ripple = repo_map.dependency_ripples.get(target_file)
        if ripple:
            score = min(5, ripple.ripple_depth)
    
    return max(1, min(5, score))


def _score_collision_risk(
    target_file: str,
    affected_modules: List[str],
    repo_map: Optional[object] = None,
) -> int:
    """
    Score collision risk: 1=low, 5=high.
    
    Mutating high-dependency zones has collision risk.
    """
    risk = 1
    
    # Risk: many modules affected
    risk += min(3, len(affected_modules) // 2)
    
    # Risk: core/infrastructure files
    if any(part in target_file for part in ['config', 'core', 'shared', 'base', '__init__', 'index.ts', 'index.js']):
        risk += 2
    
    # Risk: package.json, tsconfig, build files
    if any(target_file.endswith(ext) for ext in ['package.json', 'tsconfig.json', '.env', 'vite.config.ts']):
        risk = 5
    
    # Check for circular deps if repo_map available
    if repo_map and hasattr(repo_map, 'dependency_ripples'):
        ripple = repo_map.dependency_ripples.get(target_file)
        if ripple and ripple.circular_deps:
            risk = min(5, risk + 2)
    
    return max(1, min(5, risk))


def _apply_targeted_edit(project_id: str, op: PatchOperation) -> None:
    """Apply a targeted string replacement to an existing file."""
    content = read_file(project_id, op.relative_path)
    if op.old_string not in content:
        raise ValueError(f"String not found in {op.relative_path}: {op.old_string!r}")
    new_content = content.replace(op.old_string, op.new_string, 1)
    write_file(project_id, op.relative_path, new_content)


def _select_targets(scan: ProjectScanResult, files: list[str]) -> list[str]:
    """Select files to target based on architecture scan."""
    targets = set()

    if scan.framework == "react-vite":
        src_prefixes = ["src/"]
        targets.update(f for f in files if any(f.startswith(p) for p in src_prefixes))
    elif scan.framework == "laravel":
        laravel_targets = [
            "app/Http/Controllers",
            "resources/views",
            "routes",
            "app/Models",
        ]
        targets.update(f for f in files if any(f.startswith(t) for t in laravel_targets))
    elif scan.framework == "express":
        targets.update(f for f in files if f.endswith((".js", ".ts", ".json")))
    else:
        targets.update(f for f in files if f.endswith((".tsx", ".jsx", ".ts", ".js", ".vue", ".php")))

    return sorted(targets)
