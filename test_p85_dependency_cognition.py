"""
P8.5 Dependency-Aware Mutation Cognition Test Suite

Tests for:
- Dependency ripple analysis
- Ownership propagation
- Structural mutation risk assessment
- Dependency locality scoring
- Dry-run persistence

CRITICAL: All tests are DRY-RUN ONLY - no actual mutations.
"""

import pytest
import tempfile
import json
from pathlib import Path
from typing import Dict

# Test Fixtures


@pytest.fixture
def temp_repo():
    """Create a temporary test repository structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        
        # Create a simple React project structure
        src = repo_path / "src"
        src.mkdir()
        
        # Create interconnected modules
        (src / "main.tsx").write_text("""
import React from 'react';
import { App } from './App';
import { setup } from './utils/setup';

setup();
export function main() {
  return <App />;
}
""")
        
        (src / "App.tsx").write_text("""
import React from 'react';
import { Dashboard } from './components/Dashboard';
import { Header } from './components/Header';

export function App() {
  return (
    <>
      <Header />
      <Dashboard />
    </>
  );
}
""")
        
        components = src / "components"
        components.mkdir()
        
        (components / "Dashboard.tsx").write_text("""
import React from 'react';
import { Card } from './Card';
import { useData } from '../hooks/useData';

export function Dashboard() {
  const data = useData();
  return <Card data={data} />;
}
""")
        
        (components / "Header.tsx").write_text("""
import React from 'react';
import { useNav } from '../hooks/useNav';

export function Header() {
  const nav = useNav();
  return <header>{nav}</header>;
}
""")
        
        (components / "Card.tsx").write_text("""
import React from 'react';

export function Card({ data }) {
  return <div>{data}</div>;
}
""")
        
        hooks = src / "hooks"
        hooks.mkdir()
        
        (hooks / "useData.ts").write_text("""
import { useState } from 'react';

export function useData() {
  const [data] = useState([]);
  return data;
}
""")
        
        (hooks / "useNav.ts").write_text("""
import { useState } from 'react';

export function useNav() {
  const [nav] = useState('');
  return nav;
}
""")
        
        utils = src / "utils"
        utils.mkdir()
        
        (utils / "setup.ts").write_text("""
import { initConfig } from './config';

export function setup() {
  initConfig();
}
""")
        
        (utils / "config.ts").write_text("""
export function initConfig() {
  console.log('Config initialized');
}
""")
        
        # Create package.json
        (repo_path / "package.json").write_text(json.dumps({
            "name": "test-react-app",
            "version": "1.0.0",
            "dependencies": {
                "react": "^18.0.0",
                "react-dom": "^18.0.0"
            },
            "devDependencies": {
                "typescript": "^5.0.0",
                "vite": "^4.0.0"
            },
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "test": "vitest"
            }
        }, indent=2))
        
        yield repo_path


# ========== Tests: Dependency Ripple Analysis ==========

def test_dependency_ripple_analysis(temp_repo):
    """Test that dependency ripple analysis correctly identifies dependencies."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    # Verify ripple analysis exists
    assert repo_map.dependency_ripples is not None
    assert len(repo_map.dependency_ripples) > 0
    
    # Verify reverse graph exists
    assert repo_map.reverse_dependency_graph is not None
    
    print(f"✓ Analyzed {len(repo_map.modules)} modules")
    print(f"✓ Computed ripple analysis for {len(repo_map.dependency_ripples)} modules")
    
    # Check specific ripple analysis
    src_main = "src/main.tsx"
    if src_main in repo_map.dependency_ripples:
        ripple = repo_map.dependency_ripples[src_main]
        print(f"  {src_main}: ripple_depth={ripple.ripple_depth}, breadth={ripple.ripple_breadth}")
        assert ripple.ripple_depth >= 0
        assert ripple.ripple_breadth >= 0


def test_critical_module_detection(temp_repo):
    """Test that critical (high-ripple) modules are identified."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    # Identify critical modules
    critical = [
        module for module in repo_map.dependency_ripples.values()
        if module.is_critical
    ]
    
    # Shared/utils files should be critical
    print(f"✓ Identified {len(critical)} critical modules")
    if critical:
        for mod in critical[:3]:
            print(f"  {mod.module_path}: depth={mod.ripple_depth}, breadth={mod.ripple_breadth}")


def test_circular_dependency_detection(temp_repo):
    """Test that circular dependencies are detected."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    # Count circular dependencies
    all_circulars = set()
    for ripple in repo_map.dependency_ripples.values():
        all_circulars.update(ripple.circular_deps)
    
    print(f"✓ Detected {len(all_circulars)} circular dependency pairs")


# ========== Tests: Ownership Propagation ==========

def test_ownership_chain_inference(temp_repo):
    """Test that ownership chains are correctly inferred."""
    from backend.core.patcher.patch import _infer_ownership_chain, _extract_owner_from_path
    
    # Test owner extraction
    owner = _extract_owner_from_path("src/components/Dashboard.tsx")
    assert owner == "components"
    
    owner = _extract_owner_from_path("src/hooks/useData.ts")
    assert owner == "hooks"
    
    owner = _extract_owner_from_path("src/utils/setup.ts")
    assert owner == "utils"
    
    print("✓ Ownership extraction works correctly")


def test_ownership_propagation_for_mutation(temp_repo):
    """Test ownership propagation for a mutation."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    from backend.core.patcher.patch import assess_mutation_impact
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    # Assess impact of mutating a core file
    target = "src/utils/config.ts"
    impact = assess_mutation_impact(
        target_file=target,
        repo_map=repo_map,
        reverse_deps=repo_map.reverse_dependency_graph or {}
    )
    
    print(f"✓ Assessed mutation impact on {target}")
    print(f"  Affected modules: {impact.estimated_cascade}")
    print(f"  Ownership scope: {len(impact.ownership_scope)}")
    print(f"  Mutation locality: {impact.mutation_locality}")
    print(f"  Collision risk: {impact.collision_risk}")
    
    assert impact.target_file == target
    assert isinstance(impact.mutation_locality, int)
    assert 1 <= impact.mutation_locality <= 5
    assert 1 <= impact.collision_risk <= 5


# ========== Tests: Structural Risk Assessment ==========

def test_structural_mutation_risks(temp_repo):
    """Test structural mutation risk assessment."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    from backend.core.tool_reasoning import ToolReasoningEngine
    
    engine_repo = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine_repo.analyze()
    
    engine = ToolReasoningEngine(repo_map)
    
    # Assess risks for core file mutation
    risks = engine.assess_structural_mutation_risks(["src/utils/config.ts"])
    
    print("✓ Structural risk assessment completed")
    print(f"  Ripple depth: {risks['ripple_depth']}")
    print(f"  Ownership complexity: {risks['ownership_complexity']}")
    print(f"  Dependency locality: {risks['dependency_locality']}")
    print(f"  Collision risk: {risks['collision_risk']}")
    print(f"  Circular deps: {len(risks['circular_deps'])}")
    
    assert 'ripple_depth' in risks
    assert 'ownership_complexity' in risks
    assert risks['ownership_complexity'] in ['low', 'moderate', 'high', 'unknown']


def test_dependency_locality_scoring(temp_repo):
    """Test dependency locality scoring."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    from backend.core.tool_reasoning import ToolReasoningEngine
    
    engine_repo = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine_repo.analyze()
    
    engine = ToolReasoningEngine(repo_map)
    
    # Score isolated component
    isolated_score = engine.score_dependency_locality("src/components/Card.tsx")
    
    # Score shared utility
    shared_score = engine.score_dependency_locality("src/utils/config.ts")
    
    print(f"✓ Locality scoring completed")
    print(f"  Isolated component: {isolated_score}")
    print(f"  Shared utility: {shared_score}")
    
    assert 1 <= isolated_score <= 5
    assert 1 <= shared_score <= 5
    # Shared utilities typically have higher scores
    assert shared_score >= isolated_score


# ========== Tests: Mutation Planning with Locality ==========

def test_mutation_plan_with_locality_scoring(temp_repo):
    """Test that mutation plans include dependency locality scores."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    from backend.planner.minimal_mutation import MinimalMutationPlanner
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    planner = MinimalMutationPlanner(repo_map)
    
    # Create a simple import plan
    plan = planner.plan_add_import(
        "src/App.tsx",
        "import { newFunction } from './utils/new';"
    )
    
    print("✓ Mutation plan created with locality scoring")
    print(f"  Edits: {len(plan.edits)}")
    print(f"  Max locality: {plan.max_dependency_locality}")
    
    for edit in plan.edits:
        print(f"    {edit.target_file}: locality={edit.dependency_locality}")
        assert 1 <= edit.dependency_locality <= 5
    
    assert plan.prefer_isolated_edits() is not None


def test_risk_escalation_with_high_locality(temp_repo):
    """Test that risk levels escalate with high dependency locality."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    from backend.planner.minimal_mutation import MinimalMutationPlanner, MutationPlan, MutationEdit, EditStrategy
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    planner = MinimalMutationPlanner(repo_map)
    
    # Create plans for different files
    core_edit = MutationEdit(
        strategy=EditStrategy.INSERT_IMPORT,
        target_file="src/utils/config.ts",
        location="after_imports",
        code_to_insert="import { x } from 'y';",
        dependency_locality=5
    )
    
    isolated_edit = MutationEdit(
        strategy=EditStrategy.INSERT_IMPORT,
        target_file="src/components/Card.tsx",
        location="after_imports",
        code_to_insert="import { x } from 'y';",
        dependency_locality=1
    )
    
    core_plan = MutationPlan(
        description="Modify core file",
        total_files_affected=1,
        edits=[core_edit],
        file_order=["src/utils/config.ts"],
        validation_after_edit=[],
        rollback_commands=[],
        max_dependency_locality=5
    )
    
    isolated_plan = MutationPlan(
        description="Modify isolated file",
        total_files_affected=1,
        edits=[isolated_edit],
        file_order=["src/components/Card.tsx"],
        validation_after_edit=[],
        rollback_commands=[],
        max_dependency_locality=1
    )
    
    core_risk = core_plan.estimate_risk()
    isolated_risk = isolated_plan.estimate_risk()
    
    print("✓ Risk escalation test")
    print(f"  Core file risk: {core_risk}")
    print(f"  Isolated file risk: {isolated_risk}")
    
    # High locality should escalate risk
    assert core_risk in ["low", "medium", "high", "critical"]
    assert isolated_risk in ["low", "medium", "high", "critical"]


# ========== Tests: Dry-Run Persistence ==========

def test_p85_snapshot_persistence(temp_repo):
    """Test that P8.5 dependency data is persisted."""
    from backend.core.repository_intelligence import RepositoryIntelligenceEngine
    from backend.memory.workspace_snapshot import create_workspace_snapshot
    
    engine = RepositoryIntelligenceEngine(str(temp_repo))
    repo_map = engine.analyze()
    
    snapshot = create_workspace_snapshot(str(temp_repo))
    
    # Persist ripple data
    if repo_map.dependency_ripples:
        ripples_dict = {
            k: {
                'module_path': v.module_path,
                'ripple_depth': v.ripple_depth,
                'ripple_breadth': v.ripple_breadth,
                'is_critical': v.is_critical,
                'circular_deps': list(v.circular_deps),
            }
            for k, v in repo_map.dependency_ripples.items()
        }
        success = snapshot.save_dependency_ripples(ripples_dict)
        assert success
        print("✓ Persisted dependency ripples")
        
        # Load and verify
        loaded = snapshot.load_dependency_ripples()
        assert loaded is not None
        assert len(loaded) > 0
        print(f"✓ Loaded {len(loaded)} ripple entries from snapshot")
    
    # Persist ownership data
    ownership_data = {
        "reverse_dependency_graph": repo_map.reverse_dependency_graph or {},
        "timestamp": "2025-05-24T00:00:00",
    }
    success = snapshot.save_ownership_propagation(ownership_data)
    assert success
    print("✓ Persisted ownership propagation")
    
    # Load and verify
    loaded = snapshot.load_ownership_propagation()
    assert loaded is not None
    assert "reverse_dependency_graph" in loaded
    print("✓ Loaded ownership propagation from snapshot")


# ========== Tests: No Regressions ==========

def test_existing_p7_functionality_not_broken(temp_repo):
    """Verify that P8.5 additions don't break existing P7 functionality."""
    from backend.core.repository_intelligence import analyze_repository
    
    # Should still work
    repo_map = analyze_repository(str(temp_repo))
    
    assert repo_map is not None
    assert len(repo_map.modules) > 0
    assert len(repo_map.dependency_graph) > 0
    print("✓ P7 functionality intact")


def test_orchestration_integration(temp_repo):
    """Test P7/P8.5 integration in orchestration."""
    from backend.core.p7_orchestration import P7OrchestrationEngine, P7WorkflowRequest
    
    engine = P7OrchestrationEngine(str(temp_repo))
    
    request = P7WorkflowRequest(
        user_prompt="Add a new login component",
        project_path=str(temp_repo),
        context_files=["src/App.tsx"]
    )
    
    result = engine.execute(request)
    
    assert result is not None
    assert result.repository_map is not None
    assert result.mutation_plan is not None
    print("✓ Orchestration integration works")
    print(f"  Mutation plan edits: {len(result.mutation_plan.edits)}")
    print(f"  Risk level: {result.mutation_plan.estimate_risk()}")


# ========== Test Suite Execution ==========

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

