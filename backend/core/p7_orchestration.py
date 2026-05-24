"""
P7 Integration Layer

Wires together:
- RepositoryIntelligenceEngine
- SemanticSearchLayer
- ToolReasoningEngine
- InvestigationPlanGenerator
- MinimalMutationPlanner
- WorkspaceMemorySnapshot

Into a unified P7 orchestration flow.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class P7WorkflowRequest:
    """Input to P7 workflow."""
    user_prompt: str
    project_path: str
    context_files: List[str]  # Files the AI already has context for


@dataclass
class P7WorkflowResult:
    """Output from P7 workflow."""
    investigation_plan: Any  # InvestigationPlan
    mutation_plan: Any  # MutationPlan
    repository_map: Any  # RepositoryMap
    risk_assessment: Dict[str, Any]
    recommendations: List[str]
    confidence: float
    mutation_sequence: Optional[Any] = None  # P8.6: MutationSequence


class P7OrchestrationEngine:
    """
    Unified orchestration engine for P7 phase.
    
    Workflow:
    1. Load workspace snapshot if exists
    2. Analyze repository (or load cached)
    3. Create semantic search engine
    4. Run tool reasoning on request
    5. Generate investigation plan
    6. Generate minimal mutation plan
    7. Save workspace snapshot
    8. Return comprehensive analysis
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.repo_map = None
        self.semantic_engine = None
        self.workspace_snapshot = None
        self._init_snapshot()

    def _init_snapshot(self):
        """Initialize workspace snapshot manager."""
        from backend.memory.workspace_snapshot import create_workspace_snapshot
        self.workspace_snapshot = create_workspace_snapshot(str(self.project_path))

    def execute(self, request: P7WorkflowRequest) -> P7WorkflowResult:
        """
        Execute P7 orchestration workflow.
        
        Args:
            request: P7 workflow request
        
        Returns:
            P7WorkflowResult with complete analysis
        """
        logger.info(f"P7 Orchestration Starting: {request.user_prompt[:80]}")
        
        # Phase 1: Repository Intelligence
        logger.info("Phase 1: Repository Intelligence")
        self.repo_map = self._load_or_analyze_repo()
        
        # Phase 2: Semantic Search Engine
        logger.info("Phase 2: Semantic Search Initialization")
        self.semantic_engine = self._create_semantic_engine()
        
        # Phase 3: Tool Reasoning
        logger.info("Phase 3: Tool Reasoning")
        mutation_type = self._infer_mutation_type(request.user_prompt)
        tool_analysis = self._run_tool_reasoning(
            request.user_prompt,
            request.context_files,
            mutation_type,
        )
        
        # Phase 4: Investigation Planning
        logger.info("Phase 4: Investigation Planning")
        investigation_plan = self._generate_investigation_plan(
            request.user_prompt,
            mutation_type,
            request.context_files,
        )
        
        # Phase 5: Minimal Mutation Planning
        logger.info("Phase 5: Minimal Mutation Planning")
        mutation_plan = self._generate_mutation_plan(
            request.user_prompt,
            mutation_type,
            request.context_files,
        )
        
        # Phase 5.5 (P8.5): Dependency-Aware Mutation Cognition
        logger.info("Phase 5.5: Dependency-Aware Mutation Cognition (DRY-RUN)")
        self._enrich_with_dependency_cognition(mutation_plan, request.context_files)
        
        # Phase 5.6 (P8.6): Safe Mutation Sequencing Cognition
        logger.info("Phase 5.6: Safe Mutation Sequencing Cognition (DRY-RUN)")
        mutation_sequence = self._compute_safe_mutation_sequence(mutation_plan)
        
        # Phase 6: Persistence
        logger.info("Phase 6: Workspace Snapshot")
        self._save_workspace_snapshot()
        
        # Phase 7: Risk Assessment & Recommendations
        logger.info("Phase 7: Risk Assessment")
        risk_assessment, recommendations = self._assess_risks(
            investigation_plan,
            mutation_plan,
            tool_analysis,
        )
        
        result = P7WorkflowResult(
            investigation_plan=investigation_plan,
            mutation_plan=mutation_plan,
            repository_map=self.repo_map,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            confidence=tool_analysis.confidence,
            mutation_sequence=mutation_sequence,
        )
        
        logger.info(f"P7 Orchestration Complete - Confidence: {result.confidence:.2f}")
        return result

    # ========== PRIVATE PHASES ==========

    def _load_or_analyze_repo(self):
        """Load repo map from snapshot or analyze."""
        # Try to load from snapshot
        snapshot = self.workspace_snapshot.load_snapshot()
        if snapshot.get("repo_map"):
            logger.info("✓ Loaded repo map from snapshot")
            # Reconstruct RepositoryMap from dict
            return self._dict_to_repo_map(snapshot["repo_map"])
        
        # Otherwise analyze
        logger.info("Analyzing repository...")
        from backend.core.repository_intelligence import analyze_repository
        repo_map = analyze_repository(str(self.project_path))
        logger.info(f"✓ Repository analyzed: {repo_map.framework}")
        return repo_map

    def _create_semantic_engine(self):
        """Create semantic search engine."""
        from backend.core.semantic_search import create_semantic_search
        engine = create_semantic_search(str(self.project_path), self.repo_map.modules)
        logger.info(f"✓ Semantic engine created")
        return engine

    def _infer_mutation_type(self, prompt: str) -> str:
        """Infer mutation type from prompt."""
        from backend.core.tool_reasoning import MutationType
        
        prompt_lower = prompt.lower()
        
        # Simple heuristics
        if any(kw in prompt_lower for kw in ['add', 'create', 'new']):
            if 'component' in prompt_lower or 'page' in prompt_lower:
                return MutationType.INJECT_COMPONENT.value
            elif 'import' in prompt_lower:
                return MutationType.INSERT_IMPORT.value
            elif 'file' in prompt_lower:
                return MutationType.CREATE_NEW_FILE.value
            else:
                return MutationType.APPEND_BLOCK.value
        
        elif any(kw in prompt_lower for kw in ['modify', 'update', 'change']):
            return MutationType.MODIFY_EXISTING.value
        
        elif any(kw in prompt_lower for kw in ['replace', 'refactor', 'rewrite']):
            return MutationType.REPLACE_FILE.value
        
        else:
            return MutationType.APPEND_BLOCK.value

    def _run_tool_reasoning(
        self,
        prompt: str,
        context_files: List[str],
        mutation_type: str,
    ):
        """Run tool reasoning analysis."""
        from backend.core.tool_reasoning import (
            create_tool_reasoning_engine,
            MutationType,
        )
        
        engine = create_tool_reasoning_engine(self.repo_map, self.semantic_engine)
        
        # Convert string back to enum
        mutation_enum = MutationType(mutation_type)
        
        analysis = engine.analyze_mutation_request(
            prompt,
            context_files,
            mutation_enum,
        )
        
        logger.info(f"✓ Tool reasoning complete: Risk={analysis.risk_level.value}")
        return analysis

    def _generate_investigation_plan(
        self,
        prompt: str,
        mutation_type: str,
        context_files: List[str],
    ):
        """Generate investigation plan."""
        from backend.planner.investigation_plan import create_investigation_plan_generator
        
        gen = create_investigation_plan_generator(
            self.repo_map,
            self.semantic_engine,
        )
        
        plan = gen.generate_plan(
            prompt,
            mutation_type,
            context_files,
        )
        
        logger.info(
            f"✓ Investigation plan: "
            f"{plan.num_critical_files()} critical files, "
            f"{plan.num_high_severity_risks()} high-risk items"
        )
        return plan

    def _generate_mutation_plan(
        self,
        prompt: str,
        mutation_type: str,
        context_files: List[str],
    ):
        """Generate minimal mutation plan."""
        from backend.planner.minimal_mutation import create_minimal_mutation_planner
        
        planner = create_minimal_mutation_planner(self.repo_map)
        
        # Simple dispatch based on mutation type
        if mutation_type == "insert_import":
            # Default to adding an import (details would come from AI)
            plan = planner.plan_add_import(
                context_files[0] if context_files else "src/main.ts",
                "// import statement here",
            )
        
        elif mutation_type == "inject_component":
            plan = planner.plan_inject_react_component(
                context_files[0] if context_files else "src/App.tsx",
                "// component code here",
                "NewComponent",
            )
        
        elif mutation_type == "create_new_file":
            plan = planner.plan_create_component(
                "src/components/New.tsx",
                "// new component",
                "New",
            )
        
        else:  # append_block, modify_existing, replace_file
            plan = planner.plan_append_function(
                context_files[0] if context_files else "src/main.ts",
                "// new code here",
                "newFunction",
            )
        
        logger.info(f"✓ Mutation plan: {len(plan.edits)} edit(s), risk={plan.estimate_risk()}")
        return plan

    def _enrich_with_dependency_cognition(self, mutation_plan, context_files):
        """
        P8.5: Enrich mutation plan with dependency-aware cognition.
        
        DRY-RUN ONLY: Does not mutate, only analyzes consequences.
        
        Computes:
        - Dependency ripple graphs
        - Ownership propagation
        - Structural mutation risks
        - Dependency locality scores
        """
        logger.info("P8.5: Computing dependency ripples...")
        
        from backend.core.patcher.patch import assess_mutation_impact
        
        # For each edit target, assess mutation impact
        for edit in mutation_plan.edits:
            impact = assess_mutation_impact(
                target_file=edit.target_file,
                repo_map=self.repo_map,
                reverse_deps=self.repo_map.reverse_dependency_graph or {},
            )
            
            # Store impact in mutation plan
            mutation_plan.impact_assessments[edit.target_file] = impact
            
            logger.info(
                f"  {edit.target_file}: ripple_depth={impact.mutation_locality}, "
                f"affected_modules={impact.estimated_cascade}, "
                f"collision_risk={impact.collision_risk}"
            )
        
        # Assess structural risks using tool reasoning
        logger.info("P8.5: Assessing structural mutation risks...")
        try:
            from backend.core.tool_reasoning import ToolReasoningEngine
            
            engine = ToolReasoningEngine(self.repo_map, self.semantic_engine)
            target_files = [e.target_file for e in mutation_plan.edits]
            
            structural_risks = engine.assess_structural_mutation_risks(target_files)
            
            # Log structural insights
            logger.info(f"  Ripple Depth: {structural_risks['ripple_depth']}")
            logger.info(f"  Ownership Complexity: {structural_risks['ownership_complexity']}")
            logger.info(f"  Dependency Locality: {structural_risks['dependency_locality']}")
            logger.info(f"  Collision Risk: {structural_risks['collision_risk']}")
            
            if structural_risks['circular_deps']:
                logger.warning(f"  ⚠️  Circular dependencies detected: {len(structural_risks['circular_deps'])}")
            
            # Store in mutation plan for reporting
            mutation_plan.structural_risks = structural_risks
        except Exception as e:
            logger.warning(f"Failed to assess structural risks: {e}")
        
        logger.info("✓ P8.5 Dependency Cognition Complete (DRY-RUN)")

    def _save_workspace_snapshot(self):
        """Save workspace snapshot."""
        from backend.core.repository_intelligence import repo_map_to_dict
        
        # Build symbol index from modules
        symbol_index = {}
        for module_path, module in self.repo_map.modules.items():
            for export in module.exports:
                if export not in symbol_index:
                    symbol_index[export] = []
                symbol_index[export].append({
                    "file": module_path,
                    "type": "export",
                    "line": 0,
                })
        
        success = self.workspace_snapshot.save_snapshot(
            repo_map=repo_map_to_dict(self.repo_map),
            dependency_graph=self.repo_map.dependency_graph,
            symbol_index=symbol_index,
        )
        
        if success:
            logger.info("✓ Workspace snapshot saved to .orchestration/")
        else:
            logger.warning("⚠️  Failed to save workspace snapshot")
        
        # P8.5: Save dependency cognition data
        if self.repo_map.dependency_ripples:
            ripples_dict = {
                k: {
                    'module_path': v.module_path,
                    'direct_dependents': v.direct_dependents,
                    'transitive_dependents': v.transitive_dependents,
                    'ripple_depth': v.ripple_depth,
                    'ripple_breadth': v.ripple_breadth,
                    'is_critical': v.is_critical,
                    'circular_deps': list(v.circular_deps),
                }
                for k, v in self.repo_map.dependency_ripples.items()
            }
            self.workspace_snapshot.save_dependency_ripples(ripples_dict)
        
        if self.repo_map.reverse_dependency_graph:
            ownership_data = {
                "reverse_dependency_graph": self.repo_map.reverse_dependency_graph,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self.workspace_snapshot.save_ownership_propagation(ownership_data)

    def _assess_risks(self, investigation_plan, mutation_plan, tool_analysis) -> Tuple[Dict, List[str]]:
        """Assess risks and generate recommendations."""
        risk_assessment = {
            "investigation_confidence": investigation_plan.confidence_after_investigation,
            "mutation_risk": mutation_plan.estimate_risk(),
            "tool_confidence": tool_analysis.confidence,
            "identified_risks": len(investigation_plan.identified_risks),
            "high_severity_risks": investigation_plan.num_high_severity_risks(),
        }
        
        recommendations = []
        
        # Generate recommendations based on risks
        if investigation_plan.num_high_severity_risks() > 0:
            recommendations.append(
                f"⚠️  High severity risks detected ({investigation_plan.num_high_severity_risks()}). "
                "Review investigation plan carefully before proceeding."
            )
        
        if mutation_plan.estimate_risk() in ["high", "critical"]:
            recommendations.append(
                f"Mutation risk level: {mutation_plan.estimate_risk()}. "
                "Consider breaking into smaller changes."
            )
        
        if tool_analysis.confidence < 0.65:
            recommendations.append(
                f"Low confidence ({tool_analysis.confidence:.2f}). "
                "Run additional investigations before mutation."
            )
        
        if len(mutation_plan.edits) > 3:
            recommendations.append(
                f"Large mutation scope ({len(mutation_plan.edits)} edits). "
                "Consider splitting into multiple changes."
            )
        
        # Positive recommendations
        if len(mutation_plan.edits) == 1 and mutation_plan.estimate_risk() == "low":
            recommendations.append(
                "✓ Minimal, low-risk mutation. Safe to proceed with validation."
            )
        
        if investigation_plan.safe_to_proceed:
            recommendations.append(
                "✓ Investigation plan indicates safe to proceed."
            )
        
        return risk_assessment, recommendations

    def _dict_to_repo_map(self, repo_dict: Dict) -> Any:
        """Convert dict back to RepositoryMap object."""
        from backend.core.repository_intelligence import (
            RepositoryMap,
            ModuleInfo,
            DependencyNode,
        )
        
        modules = {}
        for path, module_dict in repo_dict.get("modules", {}).items():
            modules[path] = ModuleInfo(
                path=module_dict["path"],
                name=module_dict["name"],
                module_type=module_dict["module_type"],
                language=module_dict["language"],
                exports=module_dict["exports"],
                dependencies=module_dict["dependencies"],
                size_lines=module_dict["size_lines"],
                is_entry=module_dict.get("is_entry", False),
                is_framework=module_dict.get("is_framework", False),
            )
        
        external_deps = [
            DependencyNode(
                name=d["name"],
                version=d.get("version"),
                dep_type=d["dep_type"],
                location=d["location"],
            )
            for d in repo_dict.get("external_dependencies", [])
        ]
        
        return RepositoryMap(
            root_path=repo_dict["root_path"],
            framework=repo_dict["framework"],
            language_mix=repo_dict["language_mix"],
            modules=modules,
            entrypoints=repo_dict["entrypoints"],
            dependency_graph=repo_dict["dependency_graph"],
            external_dependencies=external_deps,
            build_commands=repo_dict["build_commands"],
            config_files=repo_dict["config_files"],
            ignore_patterns=repo_dict["ignore_patterns"],
        )


def create_p7_orchestration_engine(project_path: str) -> P7OrchestrationEngine:
    """Create P7 orchestration engine."""
    return P7OrchestrationEngine(project_path)
