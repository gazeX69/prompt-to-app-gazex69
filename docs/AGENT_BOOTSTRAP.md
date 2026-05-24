# AGENT BOOTSTRAP

**CRITICAL WARNING:** You are an AI agent continuing the development of this repository. **STOP AND READ THIS FILE IMMEDIATELY BEFORE PROCEEDING.** This file contains the foundational context required to safely mutate the workspace.

## 1. MANDATORY READING ORDER
Before making any changes to the codebase or executing terminal commands, you MUST read the following documentation files in order:
1. `docs/AGENT_BOOTSTRAP.md` (You are here)
2. `docs/AGENT_RULES.md`
3. `docs/CURRENT_STATE.md`
4. `docs/SYSTEM_ARCHITECTURE.md`
5. `docs/EXECUTION_PIPELINE.md`
6. `docs/NEXT_TARGETS.md`

## 2. CURRENT ENGINEERING PHASE
**Phase: P6.9 - Runtime Consolidated Checkpoint**
The system is currently frozen for a stable checkpoint before P7 Repository Intelligence begins. React/Vite/TypeScript execution has been stabilized through a canonical template, environment contract validation, deterministic repair behavior, formal runtime states, structured error taxonomy, dependency policy foundations, and consolidated telemetry.

**P7 REPOSITORY INTELLIGENCE HAS NOT STARTED.** Do not expand repository intelligence, add AST systems, introduce multi-framework support, or redesign orchestration while this checkpoint is being prepared.

## 3. ARCHITECTURAL INVARIANTS
- **Readonly Dominance**: The primary UI (`FileInspector`, `WorkspaceOverview`, `RepositoryExplorer`) is dense, terminal-oriented, and purely observational.
- **Single Source of Truth**: The active repository in `root/workspaces/` is the single source of truth. The backend APIs scan this directly.
- **Run Isolation**: Every orchestration operation generates artifacts inside `root/workspaces/<workspace_id>/<run_id>/.orchestration/`. Runs are immutable snapshots.
- **No AST Overhead**: File intelligence is derived using lightweight, high-speed Regex. AST frameworks are explicitly banned to maintain sub-millisecond graph compilation.
- **Canonical React/Vite Template**: `templates/react-vite-ts/` is the only authoritative React/Vite/TypeScript scaffold source.
- **Runtime Contract Authority**: Runtime states and error taxonomy are shared through `frontend/src/runtime/execution_contract.json` and loaded by backend/frontend wrappers.

## 4. FORBIDDEN ACTIONS
- **DO NOT** implement live patching or write `fs.writeFile` logic over user source files until instructed by the P11 roadmap phase.
- **DO NOT** install heavyweight dependencies like Monaco Editor, AST parsers (Babel/Esprima), or graph visualization libraries.
- **DO NOT** redesign the UI into a flashy dashboard. Maintain Codex/VSCode-style engineering density.
- **DO NOT** duplicate `.orchestration` state into separate databases.
- **DO NOT** start P7 Repository Intelligence before the P6.9 checkpoint is committed and recoverable.
- **DO NOT** add new framework support or dependency auto-install from LLM imports in this checkpoint.

## 5. MUTATION SAFETY RULES
If and when mutation is eventually authorized, patches MUST transition sequentially through:
1. `Patch Synthesized` (Raw AI output)
2. `Grounded` (Mapped to lines via context)
3. `Replay Verified` (Validated against live drift/missing symbols)
4. `Simulated` (Virtual injection and syntax sanity checked)

If a patch fails any stage, it MUST be marked `status: skipped`.
