# NEXT TARGETS

The following roadmap defines the engineering sequence to evolve the Readonly Workspace into an Autonomous Agentic Runtime. Future AI agents MUST execute these phases in order.

## Current Gate: P6.9 Checkpoint Freeze

P6.9 Runtime Consolidation is complete. The repository is currently frozen for a stable checkpoint before any P7 work begins.

Before P7 starts, the repository must preserve:
- Deterministic React/Vite/TypeScript scaffold generation from `templates/react-vite-ts/`.
- Shared runtime execution states and structured error taxonomy.
- Canonical runtime telemetry events for validation, repair, preview, and failure lifecycle.
- Dependency policy boundaries that classify undeclared imports without automatically installing packages.
- No duplicate React/Vite template authority.

P7 must not begin until this checkpoint is committed and recoverable.

## Priority Order

### P7 - Repository Intelligence Layer
- **Objective**: Extend workspace scanning beyond the current file surface to full cross-repository context.
- **Outputs**: Lightweight in-memory index mapping function signatures, types, and module responsibilities.
- **Constraints**: Maintain sub-second hydration times. Do not rely on external heavyweight vector databases. Do not alter the P6.9 runtime contract while implementing repository intelligence.

### P8 - Planning Engine
- **Objective**: Introduce an LLM-driven orchestration loop that generates `PatchOperation` structs based on user prompts.
- **Outputs**: The backend replaces the mock patches in `patch_grounding.py` with actual LLM generation.
- **Constraints**: The LLM must output structured patch targets (line ranges, symbols), not full file rewrites.

### P9 - Runtime Browser Intelligence
- **Objective**: Connect the frontend iframe preview to backend orchestration, surfacing browser console errors directly into the execution readiness matrix.
- **Outputs**: Browser error capture, DOM parsing for runtime failures.

### P10 - Failure Intelligence
- **Objective**: Build cognition around why patches fail simulation or why the browser crashes.
- **Outputs**: Failure classification structs linked to `SimulationReport`.

### P11 - Controlled Mutation Runtime
- **Objective**: Enable the system to write files to disk only after readiness gates pass.
- **Required Systems**: MUST verify that `ExecutionReadiness` is above the configured safe threshold.
- **Outputs**: The `apply_patches` function executing filesystem writes.

### P12 - Autonomous Debugging Loop
- **Objective**: Allow the AI to react to a runtime browser error by looping back through planning and controlled mutation.
- **Constraints**: Hard limits on retry loops to prevent infinite hallucination cycles.

### P13 - Specialized Multi-Agent System
- **Objective**: Split the monolithic prompt into distinct subagents: Planning Agent, Grounding Agent, Simulation Evaluator, QA Agent.

### P14 - Self-Improving Engineering Memory
- **Objective**: Persist knowledge of which patch structures consistently fail syntax sanity across projects and update prompt context to avoid repeating known mistakes.
