# CURRENT STATE

## Checkpoint Status
- Phase: P6.9 Runtime Consolidated
- Runtime Stability: Stable
- Repository Intelligence: Not Started
- Multi-framework Support: Disabled
- Execution Model: Deterministic
- Canonical Template System: Active
- Runtime Taxonomy: Active

## Overall Status
**Phase P6.9 (Runtime Consolidation) is complete and frozen for checkpoint.**

The repository is in a pre-P7 stabilization state. The React + Vite + TypeScript execution path has been made deterministic, and runtime semantics are now represented through shared machine-readable contracts. This checkpoint is a recovery point before any Repository Intelligence expansion begins.

## What is Completed
- Workspace shell, routing, and identity management.
- Backend hydration and repository tree scanning.
- Regex-based Symbol Extraction and Reference mapping.
- Blast Radius Computation (Isolated, Local, Shared, Critical dependencies).
- Structural Region Awareness (identifying Imports, Hooks, Components).
- Patch Grounding Pipeline (Context window targeting).
- Patch Replay & Drift Detection Engine (Fuzzy relocation, missing symbol trapping, duplicate injection checks).
- Virtual Patch Application (In-memory execution).
- Syntax Sanity Engine (Brace and bracket balance enforcement).
- Execution Readiness Aggregation.
- React/Vite canonical scaffold generation from `templates/react-vite-ts/`.
- React/Vite environment contract validation before install/build.
- Deterministic repair for known TypeScript and Vite ecosystem contract failures.
- Formal runtime execution states shared by backend and frontend.
- Structured React/Vite runtime error taxonomy.
- Runtime telemetry consolidation through canonical execution events.
- Minimal dependency policy foundation for declared/blocked dependency handling.

## What is Frozen
- The Architectural Orchestration layout (`.orchestration/p6`, `p65`, `p66`).
- React/Vite canonical template authority at `templates/react-vite-ts/`.
- The protected React/Vite ecosystem contract files.
- The shared runtime execution state names and transition semantics.
- The structured runtime error taxonomy used by repair, telemetry, and verification.
- The constraint against installing Heavyweight AST and graph visualizers.

## What is Disabled / Not Implemented
- Repository Intelligence (P7) has not started.
- Multi-framework support is disabled.
- Automatic dependency installation from undeclared LLM imports is not implemented.
- Package recommendation and dependency cognition are not active.
- Vector databases and heavyweight semantic indexing are not active.
- Autonomous planning expansion is not active.

## Active Risks & Known Instabilities
- The Regex parsing approach for Dependency Tracing and Region tracking is highly performant but fragile against non-standard code formatting.
- "Missing Symbol" drift logic operates on simple exact string matches. If an engineer refactors a variable name across multiple files, the patch pipeline may interpret the original target as unsafe.
- Undeclared third-party imports remain unsupported unless already declared by the canonical template or existing package manifest.
- Dependency policy is intentionally minimal: it classifies and blocks unsafe expansion but does not resolve packages automatically.
- The React/Vite path is stable; other framework paths are intentionally not covered by this checkpoint.

## React/Vite Stabilization Note
React + Vite + TypeScript generation is now stabilized around the canonical scaffold at `templates/react-vite-ts/`. The root cause fixed was ecosystem contract drift: generated feature output could overwrite `package.json`, `tsconfig*.json`, `vite.config.ts`, `index.html`, and the React mount entrypoint, which allowed invalid TypeScript project-reference shapes such as `tsc && vite build` with referenced projects and caused TS6310-style repair loops.

The React/Vite scaffold now clones the canonical template, validates the environment contract before install/build, and restores canonical config files deterministically for known TS/Vite config failures. Protected files are: `package.json`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `index.html`, and `src/main.tsx`.

Unsupported by design for this phase: automatic dependency installation from undeclared third-party imports in LLM feature files. Those failures are classified as `import_resolution_error`, but dependency expansion remains intentionally out of scope until a later controlled dependency policy exists.

## P6.9 Runtime Consolidation Note
Runtime execution now has a formal machine-readable contract at `frontend/src/runtime/execution_contract.json`. The backend loads this same contract via `backend/runtime_contract.py`, while the frontend consumes it through `frontend/src/runtime/executionContract.ts`.

The formal state model uses canonical uppercase states such as `VALIDATING`, `INSTALLING`, `BUILDING`, `STARTING_PREVIEW`, `PREVIEW_READY`, `VERIFYING`, `REPAIRING`, `FAILED`, and `COMPLETED`. Legacy lowercase state names are accepted only as aliases and normalized before telemetry is emitted.

Runtime errors now use focused React/Vite taxonomy codes such as `E_TS_REFERENCE_INVALID`, `E_IMPORT_RESOLUTION`, `E_VITE_CONFIG`, `E_REACT_ROOT_MISSING`, `E_RUNTIME_BLANK`, `E_DEPENDENCY_MISSING`, `E_BUILD_FAILURE`, and `E_PREVIEW_UNREACHABLE`. Runtime socket telemetry emits structured `execution_event` and `runtime_error` payloads for future verifiers.

React/Vite template authority is singular: `templates/react-vite-ts/` is the only template source. Backend and TypeScript runtime registries reference that canonical structure, and legacy duplicated `backend/templates/vite-react-ts/` config files have been removed to prevent drift.
