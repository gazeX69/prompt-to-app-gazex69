"""
Unit Tests for P7 Components

Quick validation of core logic without full repository scanning.
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from backend.core.tool_reasoning import (
    create_tool_reasoning_engine,
    MutationType,
    RiskLevel,
)
from backend.planner.investigation_plan import create_investigation_plan_generator
from backend.planner.minimal_mutation import (
    create_minimal_mutation_planner,
    EditStrategy,
)
from backend.memory.workspace_snapshot import create_workspace_snapshot


def test_tool_reasoning():
    """Test tool reasoning engine."""
    print("\n" + "="*60)
    print("TEST 1: Tool Reasoning Engine")
    print("="*60)
    
    try:
        engine = create_tool_reasoning_engine()
        
        # Test INSERT_IMPORT analysis
        analysis = engine.analyze_mutation_request(
            "Add React hook import",
            ["src/components/Form.tsx"],
            MutationType.INSERT_IMPORT,
        )
        
        assert analysis.mutation_type == MutationType.INSERT_IMPORT, f"Expected INSERT_IMPORT, got {analysis.mutation_type}"
        assert analysis.risk_level == RiskLevel.LOW, f"Expected LOW risk, got {analysis.risk_level}"
        assert analysis.estimated_scope == "minimal", f"Expected minimal scope, got {analysis.estimated_scope}"
        assert len(analysis.required_investigations) > 0, "No investigations generated"
        print(f"[PASS] INSERT_IMPORT: Risk={analysis.risk_level.value}, Scope={analysis.estimated_scope}")
        
        # Test INJECT_COMPONENT analysis
        analysis = engine.analyze_mutation_request(
            "Add modal dialog component",
            ["src/pages/Dashboard.tsx"],
            MutationType.INJECT_COMPONENT,
        )
        
        assert analysis.mutation_type == MutationType.INJECT_COMPONENT
        assert analysis.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        assert len(analysis.required_investigations) > 0
        print(f"✓ INJECT_COMPONENT: Risk={analysis.risk_level.value}, Scope={analysis.estimated_scope}")
        
        # Test MODIFY_EXISTING analysis
        analysis = engine.analyze_mutation_request(
            "Update authentication logic",
            ["src/services/auth.ts"],
            MutationType.MODIFY_EXISTING,
        )
        
        assert analysis.mutation_type == MutationType.MODIFY_EXISTING
        assert analysis.risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]
        assert len(analysis.required_investigations) >= 3
        print(f"✓ MODIFY_EXISTING: Risk={analysis.risk_level.value}, Investigations={len(analysis.required_investigations)}")
        
        # Test REPLACE_FILE analysis
        analysis = engine.analyze_mutation_request(
            "Refactor entire component",
            ["src/components/Complex.tsx"],
            MutationType.REPLACE_FILE,
        )
        
        assert analysis.risk_level == RiskLevel.CRITICAL
        assert analysis.confidence < 0.5  # Low confidence for replacements
        print(f"✓ REPLACE_FILE: Risk={analysis.risk_level.value}, Confidence={analysis.confidence:.2f}")
        
        print("\n✅ Tool Reasoning Engine Tests PASSED\n")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_investigation_plan_generator():
    """Test investigation plan generation."""
    print("\n" + "="*60)
    print("TEST 2: Investigation Plan Generator")
    print("="*60)
    
    try:
        gen = create_investigation_plan_generator()
        
        # Test React component addition plan
        plan = gen.generate_for_react_component_addition(
            "LoginForm",
            "App",
            ["src/App.tsx"],
        )
        
        assert plan.mutation_type == "inject_component"
        assert len(plan.file_inspections) > 0
        assert len(plan.identified_risks) > 0
        assert len(plan.validations_required) > 0
        print(f"✓ React Component Plan: {len(plan.file_inspections)} inspections, {len(plan.identified_risks)} risks")
        
        # Test API endpoint addition plan
        plan = gen.generate_for_new_api_endpoint(
            "/api/users",
            "POST",
            "routes/users.ts",
        )
        
        assert plan.mutation_type == "append_block"
        assert len(plan.commands_to_run) > 0
        print(f"✓ API Endpoint Plan: {len(plan.commands_to_run)} validation commands")
        
        # Test generic plan generation
        plan = gen.generate_plan(
            "Add dark mode support",
            "modify_existing",
            ["src/theme.ts", "src/App.tsx"],
        )
        
        assert len(plan.target_files) == 2
        assert plan.confidence_after_investigation >= 0.0
        assert plan.confidence_after_investigation <= 1.0
        print(f"✓ Generic Plan: {len(plan.target_files)} files, {len(plan.identified_risks)} risks identified")
        
        print("\n✅ Investigation Plan Generator Tests PASSED\n")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_minimal_mutation_planner():
    """Test minimal mutation planning."""
    print("\n" + "="*60)
    print("TEST 3: Minimal Mutation Planner")
    print("="*60)
    
    try:
        planner = create_minimal_mutation_planner()
        
        # Test import planning
        plan = planner.plan_add_import(
            "src/main.ts",
            "import { useEffect } from 'react';",
        )
        
        assert len(plan.edits) == 1
        assert plan.edits[0].strategy == EditStrategy.INSERT_IMPORT
        assert plan.estimate_risk() == "low"
        print(f"✓ Import Plan: {len(plan.edits)} edit(s), risk={plan.estimate_risk()}")
        
        # Test component injection planning
        plan = planner.plan_inject_react_component(
            "src/App.tsx",
            "function Modal() { return <div>Modal</div>; }",
            "Modal",
            pass_props={"isOpen": "isOpen", "onClose": "onClose"},
        )
        
        assert len(plan.edits) == 1
        assert plan.edits[0].strategy == EditStrategy.INJECT_COMPONENT
        print(f"✓ Component Injection Plan: {plan.edits[0].location}")
        
        # Test function append planning
        plan = planner.plan_append_function(
            "src/utils/helpers.ts",
            "export function formatDate(date) { return date.toISOString(); }",
            "formatDate",
        )
        
        assert len(plan.edits) == 1
        assert plan.edits[0].strategy == EditStrategy.APPEND_BLOCK
        assert plan.estimate_risk() == "low"
        print(f"✓ Function Append Plan: risk={plan.estimate_risk()}, total_lines={plan.total_lines_affected()}")
        
        # Test new component creation planning
        plan = planner.plan_create_component(
            "src/components/Button.tsx",
            "export function Button() { return <button>Click me</button>; }",
            "Button",
        )
        
        assert len(plan.edits) == 1
        assert plan.edits[0].strategy == EditStrategy.CREATE_NEW_FILE
        print(f"✓ Component Creation Plan: {plan.edits[0].target_file}")
        
        # Test strategy ranking
        strategies = [
            EditStrategy.MODIFY_MINIMAL,
            EditStrategy.INSERT_IMPORT,
            EditStrategy.CREATE_NEW_FILE,
            EditStrategy.INJECT_COMPONENT,
        ]
        ranked = planner.rank_strategies(strategies)
        
        # Verify INSERT_IMPORT ranks first
        assert ranked[0] == EditStrategy.INSERT_IMPORT
        print(f"✓ Strategy Ranking: {[s.value for s in ranked[:3]]}")
        
        print("\n✅ Minimal Mutation Planner Tests PASSED\n")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def test_workspace_snapshot():
    """Test workspace snapshot persistence."""
    print("\n" + "="*60)
    print("TEST 4: Workspace Snapshot Persistence")
    print("="*60)
    
    try:
        import tempfile
        import shutil
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = create_workspace_snapshot(tmpdir)
            
            # Save sample data
            repo_map = {
                "root_path": tmpdir,
                "framework": "react",
                "language_mix": {"typescript": 5, "javascript": 2},
                "modules": {},
                "entrypoints": ["src/main.tsx"],
                "dependency_graph": {},
                "external_dependencies": [],
                "build_commands": {"build": "vite build"},
                "config_files": ["package.json", "tsconfig.json"],
                "ignore_patterns": ["node_modules", ".git"],
            }
            
            dependency_graph = {
                "src/main.tsx": ["src/App.tsx", "react"],
                "src/App.tsx": ["src/pages/Dashboard.tsx"],
            }
            
            symbol_index = {
                "App": [{"file": "src/App.tsx", "type": "export"}],
                "Dashboard": [{"file": "src/pages/Dashboard.tsx", "type": "export"}],
            }
            
            # Save snapshot
            success = snapshot.save_snapshot(
                repo_map=repo_map,
                dependency_graph=dependency_graph,
                symbol_index=symbol_index,
            )
            assert success, "Failed to save snapshot"
            print("✓ Snapshot saved successfully")
            
            # Check status
            status = snapshot.get_snapshot_status()
            assert status["repo_map"], "Repo map not saved"
            assert status["dependency_graph"], "Dependency graph not saved"
            assert status["symbol_index"], "Symbol index not saved"
            print(f"✓ Snapshot status: {status}")
            
            # Load snapshot
            loaded = snapshot.load_snapshot()
            assert loaded["repo_map"] is not None
            assert loaded["repo_map"]["framework"] == "react"
            print(f"✓ Snapshot loaded: framework={loaded['repo_map']['framework']}")
            
            # Test investigation caching
            investigation_cache = {
                "find_components": [
                    {
                        "timestamp": "2026-05-23T12:00:00",
                        "query": "React components",
                        "result": {"count": 5, "components": ["App", "Modal", "Form"]},
                    }
                ]
            }
            
            snapshot.save_investigation_cache(investigation_cache)
            cached = snapshot.load_investigation_cache()
            assert "find_components" in cached
            print("✓ Investigation cache saved and loaded")
            
            # Test hash generation
            hash1 = snapshot.get_snapshot_hash()
            assert hash1 is not None
            assert len(hash1) == 32  # MD5 hash length
            print(f"✓ Snapshot hash: {hash1[:16]}...")
            
            # Save again and verify hash changes
            investigation_cache["new_result"] = "test"
            snapshot.save_investigation_cache(investigation_cache)
            hash2 = snapshot.get_snapshot_hash()
            assert hash2 != hash1, "Hash should change after modification"
            print(f"✓ Hash changed after modification: {hash2[:16]}...")
        
        print("\n✅ Workspace Snapshot Tests PASSED\n")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all unit tests."""
    print("\n" + "="*60)
    print("P7 UNIT TEST SUITE")
    print("="*60)
    
    tests = [
        ("Tool Reasoning Engine", test_tool_reasoning),
        ("Investigation Plan Generator", test_investigation_plan_generator),
        ("Minimal Mutation Planner", test_minimal_mutation_planner),
        ("Workspace Snapshot Persistence", test_workspace_snapshot),
    ]
    
    results = {}
    for name, test_func in tests:
        results[name] = test_func()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    total_passed = sum(1 for p in results.values() if p)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL P7 UNIT TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
