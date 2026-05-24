# SYSTEM ARCHITECTURE

## 1. High-Level Topology
The system is divided into two primary decoupled layers:
- **Frontend Observability Shell**: A React/Vite application utilizing Zustand for state management and Tailwind CSS for styling. It acts as a purely readonly window into the repository's intelligence and the orchestration engine's cognitive state.
- **Backend Orchestration Engine**: A FastAPI Python backend responsible for workspace hydration, repository scanning, reference graph building, patch simulation, and telemetry aggregation.

## 2. Component Relationships
### Frontend
- **`workspace.store.ts`**: The central nervous system. Manages the active workspace identity, run history, and repository directory trees. Exposes `loadWorkspace` and `loadRunData`.
- **`WorkspaceOverview.tsx`**: The top-level dashboard. Displays system telemetry, `execution_readiness_score`, and run history timelines.
- **`RepositoryExplorer.tsx`**: A hierarchical file tree that overlays "operational heat" (Blast Radius indicators: red/yellow/blue dots) derived from the backend dependency graph.
- **`FileInspector.tsx`**: The deepest cognition view. When a file is selected, it lazily queries the backend for Symbols, References (Imports/Export relationships), Regions (structural block boundaries), Patches (pending operations), Replays (drift adjustments), and Simulations (virtual execution diffs).

### Backend
- **`workspace_scanner.py`**: Reads `root/workspaces/<workspace_id>/` and constructs virtual representations of the file tree. Calculates `get_workspace_references` by executing rapid cross-file Regex searches to determine dependency depth and blast radius score.
- **`patch_grounding.py`**: Executes `detect_file_regions` to find imports, components, and hooks. Implements `evaluate_patch_replay` to fuzzily relocate drifting patches against the live file content and catch collision scenarios.
- **`patch_simulation.py`**: Implements `simulate_patch_application` which performs in-memory string injections and runs `run_syntax_sanity` to prevent brace/bracket imbalance.
- **`execution_readiness.py`**: Aggregates the simulation and replay data to output a holistic `execution_readiness_score`.

## 3. Storage and Persistence
- **Source of Truth**: The active repository files located in `<root>/workspaces/`.
- **Orchestration Artifacts**: AI cognitive data is persisted inside `<root>/workspaces/<workspace_id>/<run_id>/.orchestration/`.
  - `p6/patches.json`: Raw grounded target intents.
  - `p65/replays.json`: Evaluated safety matrices and fuzzy relocation offsets.
  - `p66/simulations.json`: Syntax sanity outcomes and virtual diff statistics.

## 4. Execution Flow
1. User loads a Workspace -> Frontend requests `/workspaces/{id}`.
2. Backend returns Workspace Metadata + Run History + `latest` tree.
3. User navigates `RepositoryExplorer` -> Backend dynamically computes `Blast Radius` for tree nodes.
4. User clicks a File -> `FileInspector` fires 5 parallel API requests for deep file intelligence.
5. Backend pulls from `.orchestration/` to deliver Replay/Simulation data. Frontend merges arrays via `patch_id`.

## 5. React/Vite Runtime Path
The deterministic React/Vite/TypeScript path is a constrained execution lane, not a general framework generator.

- **Canonical template:** `templates/react-vite-ts/` is the only authoritative React/Vite scaffold source.
- **Backend registry:** `backend/templates/registry.py` references the canonical template instead of duplicating ecosystem config.
- **Runtime registry:** `runtime/src/templates/TemplateRegistry.ts` references the same canonical structure.
- **Environment validator:** `backend/templates/react_vite_contract.py` validates TypeScript config, Vite config, package scripts, dependencies, entrypoints, and React mount target before install/build.
- **Protected files:** `package.json`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `index.html`, and `src/main.tsx` are treated as ecosystem contracts.
- **Deterministic repair:** Known config failures restore canonical files instead of delegating repair to LLM generation.

## 6. Runtime Contract and Telemetry
Runtime semantics are shared through `frontend/src/runtime/execution_contract.json`.

- **Backend loader:** `backend/runtime_contract.py` loads the same state and error taxonomy used by the frontend.
- **Frontend loader:** `frontend/src/runtime/executionContract.ts` exposes canonical states, error codes, and aliases to UI stores.
- **Execution states:** Runtime lifecycle events use uppercase canonical states such as `VALIDATING`, `INSTALLING`, `BUILDING`, `STARTING_PREVIEW`, `PREVIEW_READY`, `VERIFYING`, `REPAIRING`, `FAILED`, and `COMPLETED`.
- **Error taxonomy:** React/Vite runtime failures emit structured codes such as `E_TS_REFERENCE_INVALID`, `E_IMPORT_RESOLUTION`, `E_VITE_CONFIG`, `E_REACT_ROOT_MISSING`, `E_RUNTIME_BLANK`, `E_DEPENDENCY_MISSING`, `E_BUILD_FAILURE`, and `E_PREVIEW_UNREACHABLE`.
- **Socket telemetry:** Backend socket messages emit machine-readable `execution_event` and `runtime_error` payloads. Frontend consumers normalize legacy aliases into canonical states.

## 7. Dependency Policy Foundation
Dependency handling remains intentionally conservative.

- Dependencies declared by the canonical template are allowed.
- Known blocked dependencies can be classified without executing installation.
- Undeclared third-party imports are classified as dependency/import failures.
- Automatic package installation from LLM output is unsupported in this checkpoint.
