# P7 Phase: Repository Intelligence & Tool Reasoning

## Overview

**P7** transitions the AI from prompt-driven generation toward workspace-aware engineering reasoning.

The system learns to:
- Inspect repositories systematically
- Reason about tools before mutation
- Minimize mutation scope
- Choose investigation strategies before patching

## Architecture

### Core Components

#### 1. **RepositoryIntelligenceEngine** (`backend/core/repository_intelligence.py`)

Performs comprehensive repository analysis without relying on filename matching alone.

**Capabilities:**
- Recursive repository scanning
- Module ownership detection
- Dependency graph extraction
- Entrypoint detection
- Framework detection (React, Vue, Node, Express, PHP, Django, etc.)
- Build/test command detection
- Config file discovery
- Import graph mapping

**Usage:**
```python
from backend.core.repository_intelligence import analyze_repository, repo_map_to_dict

repo_map = analyze_repository("/path/to/project")
# repo_map.framework == "react"
# repo_map.modules == {file_path: ModuleInfo, ...}
# repo_map.dependency_graph == {module: [imports], ...}
# repo_map.entrypoints == ["src/main.tsx", ...]
```

**Output:** `RepositoryMap` containing all repository metadata

---

#### 2. **SemanticSearchLayer** (`backend/core/semantic_search.py`)

Locates symbols, components, routes, and API handlers without text-only matching.

**Capabilities:**
- Symbol definition location
- Symbol usage tracing
- React/Vue component discovery
- API route detection
- Dependency chain tracing
- Import/export analysis

**Usage:**
```python
from backend.core.semantic_search import create_semantic_search

semantic = create_semantic_search(repo_path, repo_map.modules)

# Find components
components = semantic.find_components("typescript")
# Returns: [ComponentLocation(name, props, children, imports, ...)]

# Trace dependencies
chain = semantic.trace_dependency_chain("App", "Modal")
# Returns: ImportChain with breadcrumb trail
```

**Output:** Symbol locations, component trees, route definitions, dependency chains

---

#### 3. **ToolReasoningEngine** (`backend/core/tool_reasoning.py`)

Reasons about WHEN to use investigation tools before mutations.

**Decision Logic:**
- `INSERT_IMPORT` → LOW risk → minimal investigations
- `INJECT_COMPONENT` → MEDIUM risk → inspect parent component
- `APPEND_BLOCK` → MEDIUM risk → check scope and dependencies
- `MODIFY_EXISTING` → HIGH risk → trace usages, review tests
- `REPLACE_FILE` → CRITICAL risk → extensive analysis required

**Usage:**
```python
from backend.core.tool_reasoning import create_tool_reasoning_engine, MutationType

engine = create_tool_reasoning_engine(repo_map, semantic)

analysis = engine.analyze_mutation_request(
    "Add login form",
    ["src/App.tsx"],
    MutationType.INJECT_COMPONENT,
)
# Returns: ToolReasoningAnalysis with:
# - risk_level: RiskLevel.MEDIUM
# - required_investigations: [InvestigationAction, ...]
# - mutation_risks: [str, ...]
# - confidence: 0.70
```

**Output:** `ToolReasoningAnalysis` with investigation requirements

---

#### 4. **InvestigationPlanGenerator** (`backend/planner/investigation_plan.py`)

Generates detailed investigation plans before patch generation.

**Plan Includes:**
- Files to inspect with priorities
- Symbols to trace
- Validation commands to run
- Validation scenarios that must pass
- Identified mutation risks

**Usage:**
```python
from backend.planner.investigation_plan import create_investigation_plan_generator

gen = create_investigation_plan_generator(repo_map, semantic, tool_engine)

plan = gen.generate_for_react_component_addition(
    "LoginForm",
    "App",
    ["src/App.tsx"],
)
# Returns: InvestigationPlan with:
# - file_inspections: [FileInspection, ...]
# - symbol_traces: [SymbolTrace, ...]
# - validations_required: [ValidationScenario, ...]
# - identified_risks: [MutationRisk, ...]
# - safe_to_proceed: bool
```

**Output:** `InvestigationPlan` ready for execution

---

#### 5. **MinimalMutationPlanner** (`backend/planner/minimal_mutation.py`)

Plans mutations using surgical edits, not broad rewrites.

**Strategy Hierarchy (preferred order):**
1. `INSERT_IMPORT` - Non-intrusive
2. `APPEND_BLOCK` - Non-destructive
3. `CREATE_NEW_FILE` - Isolated
4. `INJECT_COMPONENT` - Localized impact
5. `INSERT_HOOK` - Requires context
6. `MODIFY_MINIMAL` - Precision required
7. `PREPEND_BLOCK` - Affects line numbers
8. `INJECT_MIDDLEWARE` - Complex flow
9. ❌ AVOID: Full file replacement

**Usage:**
```python
from backend.planner.minimal_mutation import create_minimal_mutation_planner

planner = create_minimal_mutation_planner(repo_map)

# Plan import insertion
plan = planner.plan_add_import(
    "src/main.ts",
    "import { useEffect } from 'react';",
)
# Returns: MutationPlan with 1 low-risk edit

# Plan component injection
plan = planner.plan_inject_react_component(
    "src/App.tsx",
    "function Modal() { ... }",
    "Modal",
    pass_props={"isOpen": "isOpen"},
)
# Returns: MutationPlan with localized edit
```

**Output:** `MutationPlan` with minimal edits

---

#### 6. **WorkspaceMemorySnapshot** (`backend/memory/workspace_snapshot.py`)

Persists intelligence data to disk for future reference.

**Persistence:**
- `.orchestration/repo_map.json` - Repository structure
- `.orchestration/dependency_graph.json` - Import graph
- `.orchestration/symbol_index.json` - Symbol ownership
- `.orchestration/investigation_cache.json` - Recent findings
- `.orchestration/metadata.json` - Snapshot metadata

**Usage:**
```python
from backend.memory.workspace_snapshot import create_workspace_snapshot

snapshot = create_workspace_snapshot(project_path)

# Save everything
snapshot.save_snapshot(
    repo_map=repo_map_dict,
    dependency_graph=dep_graph,
    symbol_index=symbol_index,
)

# Load later
loaded = snapshot.load_snapshot()
# Returns: {
#   "repo_map": {...},
#   "dependency_graph": {...},
#   "symbol_index": {...},
#   "investigation_cache": {...},
# }

# Cache investigation results
snapshot.save_investigation_result(
    "find_components",
    {"count": 5, "components": ["App", "Modal", ...]},
    "React components",
)
```

**Output:** Persistent .orchestration/ directory

---

#### 7. **P7OrchestrationEngine** (`backend/core/p7_orchestration.py`)

Unified orchestration engine that wires all P7 components together.

**Workflow:**
1. Load workspace snapshot (if exists)
2. Analyze repository (or load cached)
3. Create semantic search engine
4. Run tool reasoning on request
5. Generate investigation plan
6. Generate minimal mutation plan
7. Save workspace snapshot
8. Assess risks and generate recommendations

**Usage:**
```python
from backend.core.p7_orchestration import create_p7_orchestration_engine, P7WorkflowRequest

engine = create_p7_orchestration_engine(project_path)

result = engine.execute(P7WorkflowRequest(
    user_prompt="Add a login form to the app",
    project_path=project_path,
    context_files=["src/App.tsx"],
))

# Returns: P7WorkflowResult with:
# - investigation_plan: InvestigationPlan
# - mutation_plan: MutationPlan
# - repository_map: RepositoryMap
# - risk_assessment: {confidence, risks, etc.}
# - recommendations: [str, ...]
# - confidence: float
```

---

## Integration Points

### With Existing Orchestrator (`backend/orchestrator/project_orchestrator.py`)

P7 components should be integrated at these stages:

```python
async def generate_code_with_p7(project_id, run_id, prompt, ecosystem):
    """Generate code with P7 intelligence."""
    
    # 1. Get project path
    project_path = f"workspaces/{project_id}"
    
    # 2. Execute P7 orchestration
    p7_engine = create_p7_orchestration_engine(project_path)
    p7_result = p7_engine.execute(P7WorkflowRequest(
        user_prompt=prompt,
        project_path=project_path,
        context_files=["src/main.tsx"],  # placeholder
    ))
    
    # 3. Log analysis results
    await emit_agent_activity(
        f"Investigation completed: {p7_result.risk_assessment}",
        project_id,
    )
    
    # 4. Use investigation plan to inform AI
    investigation_context = format_investigation_for_prompt(p7_result)
    
    # 5. Generate code with investigation context
    ai_prompt = build_ai_prompt(
        user_prompt=prompt,
        investigation_plan=p7_result.investigation_plan,
        mutation_plan=p7_result.mutation_plan,
        confidence=p7_result.confidence,
    )
    
    # 6. Execute generation with smaller, safer mutations
    code_output = await complete(ai_prompt)
    
    # 7. Validate against investigation plan
    validation_results = validate_against_plan(
        code_output,
        p7_result.investigation_plan.validations_required,
    )
```

### Logging & Observability

All P7 components log via Python's standard logging:

```python
import logging

logger = logging.getLogger(__name__)

# Enable verbose P7 logging
logging.getLogger("backend.core.repository_intelligence").setLevel(logging.DEBUG)
logging.getLogger("backend.core.semantic_search").setLevel(logging.DEBUG)
logging.getLogger("backend.core.tool_reasoning").setLevel(logging.DEBUG)
```

### WebSocket Emission

Emit P7 analysis results to frontend:

```python
from backend.sockets.manager import emit_agent_activity

await emit_agent_activity(
    f"P7 Analysis: "
    f"Risk={p7_result.risk_assessment['mutation_risk']}, "
    f"Confidence={p7_result.confidence:.2f}, "
    f"Mutations={len(p7_result.mutation_plan.edits)}",
    project_id,
)
```

---

## Success Criteria

P7 succeeds only if:

✅ **Repository awareness**
  - RepositoryIntelligenceEngine correctly identifies framework
  - All modules indexed with exports/imports
  - Dependency graph populated

✅ **Semantic tracing**
  - Components located without filename-only matching
  - Symbol usages traced across files
  - Routes detected and mapped

✅ **Tool reasoning**
  - Different mutation types mapped to different risk levels
  - Required investigations generated before mutations
  - Confidence scores reflect actual analysis depth

✅ **Investigation-first cognition**
  - Mutations are NOT generated until investigation plan exists
  - Investigation results logged and cached
  - AI uses investigation context in generation prompts

✅ **Minimal mutation scopes**
  - Multi-edit plans are rare
  - `INSERT_IMPORT` and `APPEND_BLOCK` preferred
  - File replacements avoided or heavily warned

✅ **Workspace snapshots**
  - `.orchestration/` directory created and populated
  - Snapshots speed up repeat analysis
  - Change detection via snapshot hash

✅ **No regressions**
  - All existing tests pass
  - Generation quality maintained or improved
  - Build/deployment process unchanged

---

## Testing

### Unit Tests (`test_p7_units.py`)

Quick validation of core logic:

```bash
python test_p7_units.py

# Output:
# ✅ PASS: Tool Reasoning Engine
# ✅ PASS: Investigation Plan Generator
# ✅ PASS: Minimal Mutation Planner
# ✅ PASS: Workspace Snapshot Persistence
```

### Full Integration Test (`test_p7_validation.py`)

End-to-end validation with real workspaces:

```bash
python test_p7_validation.py

# Tests:
# 1. React Todo App - Repository mapping
# 2. PHP Login App - Framework detection
# 3. Multi-Component React - Dependency tracing
```

---

## Performance Considerations

### Caching Strategy

1. **First run**: Full analysis takes ~2-5 seconds depending on codebase
2. **Cached loads**: Snapshot loading takes <100ms
3. **Incremental updates**: Can reuse cached analyses if no file changes

### Optimization Opportunities

- Lazy-load semantic search only when needed
- Cache symbol indices for large codebases
- Use .orchestration/metadata.json to detect file changes
- Parallel file scanning in future phases

---

## Important Notes

### NOT Included in P7

❌ Autonomous execution (mutations are AI-generated but human-validated)
❌ Automatic rollback systems (manual git rollback available)
❌ Self-repair loops (analysis only, no auto-fixes)
❌ Multi-agent systems (single AI agent with better tools)
❌ New ecosystems (React, Node, PHP, Python only)

### These Remain Unchanged

✓ Runtime execution (sandbox/executor.py)
✓ Preview systems (dev servers)
✓ Artifact tracking
✓ Patch simulation
✓ Build/test infrastructure

---

## Future Extensions (P8+)

Once P7 is mature:

1. **Autonomous Repair Loops** - Iterate on failed mutations automatically
2. **Parallel Analysis** - Multi-threaded repository scanning
3. **Test-Driven Mutation** - Generate tests before mutations
4. **Capability Expansion** - Add more languages/frameworks
5. **Cost Optimization** - Minimize AI token usage through better context

---

## References

- Repository Intelligence: `backend/core/repository_intelligence.py`
- Semantic Search: `backend/core/semantic_search.py`
- Tool Reasoning: `backend/core/tool_reasoning.py`
- Investigation Planning: `backend/planner/investigation_plan.py`
- Minimal Mutation: `backend/planner/minimal_mutation.py`
- Workspace Snapshots: `backend/memory/workspace_snapshot.py`
- P7 Orchestration: `backend/core/p7_orchestration.py`
