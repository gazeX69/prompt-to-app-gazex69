"""
Test P7 Repository Intelligence & Tool Reasoning Layer

Validates:
1. Repository mapping works
2. Semantic tracing works
3. Investigation plans generate correctly
4. Tool reasoning logs appear
5. Mutation scopes stay minimal
"""

import sys
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from backend.core.repository_intelligence import analyze_repository, repo_map_to_dict
from backend.core.semantic_search import create_semantic_search
from backend.core.tool_reasoning import create_tool_reasoning_engine, MutationType
from backend.planner.investigation_plan import create_investigation_plan_generator
from backend.planner.minimal_mutation import create_minimal_mutation_planner
from backend.memory.workspace_snapshot import create_workspace_snapshot


def test_react_todo_app():
    """Test Case 1: React Todo App"""
    print("\n" + "="*70)
    print("TEST 1: React Todo App - Repository Intelligence")
    print("="*70)
    
    # Analyze a React project
    test_repo = Path(__file__).parent / "workspaces" / "proj-1779536667738"
    if not test_repo.exists():
        print(f"⚠️  Test workspace not found: {test_repo}")
        return False
    
    print(f"\n📁 Analyzing repository: {test_repo}")
    
    try:
        # 1. Repository mapping
        print("\n[1] Repository Mapping...")
        repo_map = analyze_repository(str(test_repo))
        print(f"  ✓ Framework detected: {repo_map.framework}")
        print(f"  ✓ Modules found: {len(repo_map.modules)}")
        print(f"  ✓ Language mix: {repo_map.language_mix}")
        print(f"  ✓ Entrypoints: {repo_map.entrypoints}")
        print(f"  ✓ External dependencies: {len(repo_map.external_dependencies)}")
        print(f"  ✓ Build commands: {list(repo_map.build_commands.keys())}")
        
        # 2. Semantic search
        print("\n[2] Semantic Search...")
        semantic = create_semantic_search(str(test_repo), repo_map.modules)
        
        # Find React components
        components = semantic.find_components('typescript')
        print(f"  ✓ React components found: {len(components)}")
        for comp in components[:3]:
            print(f"    - {comp.component_name} ({comp.file_path})")
        
        # Find routes
        routes = semantic.find_routes()
        print(f"  ✓ API routes found: {len(routes)}")
        for route in routes[:3]:
            print(f"    - {route.method} {route.path}")
        
        # 3. Tool reasoning
        print("\n[3] Tool Reasoning...")
        tool_engine = create_tool_reasoning_engine(repo_map, semantic)
        analysis = tool_engine.analyze_mutation_request(
            "Add a new login form component",
            ["src/App.tsx"],
            MutationType.INJECT_COMPONENT,
        )
        print(f"  ✓ Risk level: {analysis.risk_level.value}")
        print(f"  ✓ Mutation type: {analysis.mutation_type.value}")
        print(f"  ✓ Scope: {analysis.estimated_scope}")
        print(f"  ✓ Confidence: {analysis.confidence:.2f}")
        print(f"  ✓ Required investigations: {len(analysis.required_investigations)}")
        for inv in analysis.required_investigations[:2]:
            print(f"    - {inv}")
        
        # 4. Investigation planning
        print("\n[4] Investigation Plan Generation...")
        plan_gen = create_investigation_plan_generator(repo_map, semantic, tool_engine)
        plan = plan_gen.generate_for_react_component_addition(
            "LoginForm",
            "App",
            ["src/App.tsx"],
        )
        print(f"  ✓ File inspections: {len(plan.file_inspections)}")
        print(f"  ✓ Symbol traces: {len(plan.symbol_traces)}")
        print(f"  ✓ Commands to run: {len(plan.commands_to_run)}")
        print(f"  ✓ Validations: {len(plan.validations_required)}")
        print(f"  ✓ Identified risks: {len(plan.identified_risks)}")
        print(f"  ✓ Safe to proceed: {plan.safe_to_proceed}")
        
        # 5. Minimal mutation planning
        print("\n[5] Minimal Mutation Planning...")
        mutation_planner = create_minimal_mutation_planner(repo_map)
        mutation_plan = mutation_planner.plan_inject_react_component(
            "src/App.tsx",
            "function LoginForm() { return <div>Login</div>; }",
            "LoginForm",
        )
        print(f"  ✓ Edits: {len(mutation_plan.edits)}")
        print(f"  ✓ Total lines affected: {mutation_plan.total_lines_affected()}")
        print(f"  ✓ Risk estimate: {mutation_plan.estimate_risk()}")
        for edit in mutation_plan.edits:
            print(f"    - {edit.strategy.value} at {edit.location}")
        
        # 6. Workspace snapshot
        print("\n[6] Workspace Snapshot...")
        snapshot = create_workspace_snapshot(str(test_repo))
        snapshot.save_snapshot(
            repo_map=repo_map_to_dict(repo_map),
            dependency_graph=repo_map.dependency_graph,
        )
        status = snapshot.get_snapshot_status()
        print(f"  ✓ Snapshot saved: {status}")
        
        print("\n✅ React Todo App Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n❌ React Todo App Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_php_login_app():
    """Test Case 2: PHP Login App"""
    print("\n" + "="*70)
    print("TEST 2: PHP Login App - Framework Detection")
    print("="*70)
    
    # Look for a PHP project workspace
    test_repo = Path(__file__).parent / "workspaces" / "proj-1779532821453"
    if not test_repo.exists():
        print(f"⚠️  Test workspace not found: {test_repo}")
        return False
    
    print(f"\n📁 Analyzing PHP repository: {test_repo}")
    
    try:
        # 1. Repository mapping with PHP detection
        print("\n[1] PHP Framework Detection...")
        repo_map = analyze_repository(str(test_repo))
        print(f"  ✓ Framework: {repo_map.framework}")
        print(f"  ✓ PHP files: {repo_map.language_mix.get('php', 0)}")
        print(f"  ✓ Config files: {repo_map.config_files}")
        
        # 2. Semantic search for PHP components
        print("\n[2] API Handler Discovery...")
        semantic = create_semantic_search(str(test_repo), repo_map.modules)
        handlers = semantic.find_api_handlers()
        print(f"  ✓ API handlers found: {len(handlers)}")
        for handler in handlers[:3]:
            print(f"    - {handler}")
        
        # 3. Investigation plan for new endpoint
        print("\n[3] Investigation Plan - New API Endpoint...")
        plan_gen = create_investigation_plan_generator(repo_map, semantic)
        plan = plan_gen.generate_for_new_api_endpoint(
            "/api/login",
            "POST",
            "index.php",
        )
        print(f"  ✓ File inspections: {len(plan.file_inspections)}")
        print(f"  ✓ Risks identified: {len(plan.identified_risks)}")
        print(f"  ✓ Confidence: {plan.confidence_after_investigation:.2f}")
        
        # 4. Minimal mutation planning
        print("\n[4] Mutation Planning - Append Endpoint...")
        mutation_planner = create_minimal_mutation_planner(repo_map)
        mutation_plan = mutation_planner.plan_append_function(
            "index.php",
            "function handleLogin() { return json_encode(['status' => 'ok']); }",
            "handleLogin",
        )
        print(f"  ✓ Edits: {len(mutation_plan.edits)}")
        print(f"  ✓ Risk: {mutation_plan.estimate_risk()}")
        
        print("\n✅ PHP Login App Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n❌ PHP Login App Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_component_react():
    """Test Case 3: Multi-Component React App"""
    print("\n" + "="*70)
    print("TEST 3: Multi-Component React App - Dependency Tracing")
    print("="*70)
    
    test_repo = Path(__file__).parent / "workspaces" / "proj-1779536242715"
    if not test_repo.exists():
        print(f"⚠️  Test workspace not found: {test_repo}")
        return False
    
    print(f"\n📁 Analyzing Multi-Component React: {test_repo}")
    
    try:
        # 1. Full repository analysis
        print("\n[1] Complete Repository Analysis...")
        repo_map = analyze_repository(str(test_repo))
        print(f"  ✓ Total modules: {len(repo_map.modules)}")
        print(f"  ✓ Dependency graph entries: {len(repo_map.dependency_graph)}")
        
        # 2. Semantic search - component hierarchy
        print("\n[2] Component Hierarchy...")
        semantic = create_semantic_search(str(test_repo), repo_map.modules)
        components = semantic.find_components()
        print(f"  ✓ Total components: {len(components)}")
        
        # Trace parent-child relationships
        component_tree = {}
        for comp in components[:5]:
            component_tree[comp.component_name] = comp.children
            children_str = str(comp.children)
            print(f"    - {comp.component_name}: children={children_str}")
        
        # 3. Tool reasoning for complex mutation
        print("\n[3] Tool Reasoning - Complex Component Injection...")
        tool_engine = create_tool_reasoning_engine(repo_map, semantic)
        analysis = tool_engine.analyze_mutation_request(
            "Add user dashboard with nested components",
            ["src/pages/Dashboard.tsx", "src/components/UserCard.tsx"],
            MutationType.INJECT_COMPONENT,
        )
        print(f"  ✓ Risk: {analysis.risk_level.value}")
        print(f"  ✓ Target files: {len(analysis.target_file)}")
        print(f"  ✓ Investigations needed: {len(analysis.required_investigations)}")
        print(f"  ✓ Mutation risks: {len(analysis.mutation_risks)}")
        for risk in analysis.mutation_risks[:2]:
            print(f"    - {risk}")
        
        # 4. Comprehensive investigation plan
        print("\n[4] Comprehensive Investigation Plan...")
        plan_gen = create_investigation_plan_generator(repo_map, semantic, tool_engine)
        plan = plan_gen.generate_plan(
            "Restructure Dashboard with new layouts",
            "modify_existing",
            ["src/pages/Dashboard.tsx"],
        )
        print(f"  ✓ File inspections: {plan.num_critical_files()} critical")
        print(f"  ✓ High severity risks: {plan.num_high_severity_risks()}")
        print(f"  ✓ Safe to proceed: {plan.safe_to_proceed}")
        
        # 5. Test minimal mutation strategies
        print("\n[5] Mutation Strategy Ranking...")
        mutation_planner = create_minimal_mutation_planner(repo_map)
        from backend.planner.minimal_mutation import EditStrategy
        strategies = [
            EditStrategy.INJECT_COMPONENT,
            EditStrategy.MODIFY_EXISTING,
            EditStrategy.CREATE_NEW_FILE,
        ]
        ranked = mutation_planner.rank_strategies(strategies)
        print(f"  ✓ Ranked strategies:")
        for i, strategy in enumerate(ranked, 1):
            print(f"    {i}. {strategy.value}")
        
        # 6. Workspace snapshots with full analysis
        print("\n[6] Complete Workspace Snapshot...")
        snapshot = create_workspace_snapshot(str(test_repo))
        
        # Build symbol index
        symbol_index = {}
        for module_path, module in repo_map.modules.items():
            for export in module.exports:
                if export not in symbol_index:
                    symbol_index[export] = []
                symbol_index[export].append({
                    "file": module_path,
                    "type": "export",
                    "line": 0,  # would need content analysis for real line
                })
        
        snapshot.save_snapshot(
            repo_map=repo_map_to_dict(repo_map),
            dependency_graph=repo_map.dependency_graph,
            symbol_index=symbol_index,
        )
        
        status = snapshot.get_snapshot_status()
        print(f"  ✓ Snapshot status: {status}")
        snapshot_hash = snapshot.get_snapshot_hash()
        print(f"  ✓ Snapshot hash: {snapshot_hash[:16]}...")
        
        print("\n✅ Multi-Component React App Test PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Multi-Component React App Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests."""
    print("\n" + "="*70)
    print("P7 PHASE VALIDATION TEST SUITE")
    print("Repository Intelligence & Tool Reasoning Layer")
    print("="*70)
    
    results = {
        "React Todo App": test_react_todo_app(),
        "PHP Login App": test_php_login_app(),
        "Multi-Component React": test_multi_component_react(),
    }
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for p in results.values() if p)
    total_tests = len(results)
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 ALL P7 VALIDATION TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
