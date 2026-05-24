# EXECUTION PIPELINE

This document traces the exact path a piece of generated code must take before it is permitted to alter a user's repository.

## Step 1: Grounding (P6)
* **Location:** `backend/core/scanner/patch_grounding.py`
* **Action:** The system maps the raw AI patch intent to specific structural blocks (e.g., `imports_zone`, `component_zone`) within the target file.
* **Output:** A `PatchOperation` payload with exact line coordinates (`target_region`) and structural anchors (`grounding_context`).

## Step 2: Replay Validation (P6.5)
* **Location:** `backend/core/scanner/patch_grounding.py` (evaluate_patch_replay)
* **Action:** The system checks if the file has changed since the patch was planned. It fuzzily relocates the target region if the file shifted, traps missing symbols, and flags duplicate imports.
* **Output:** A `ReplayReport` scoring the patch as `safe`, `degraded`, or `unsafe`.

## Step 3: Virtual Simulation (P6.6)
* **Location:** `backend/core/scanner/patch_simulation.py`
* **Action:** The system generates an in-memory string copy of the file and virtually applies the patch.
* **Output:** A `SimulationReport` that validates bracket/brace equilibrium (`syntax_sanity`) and computes the exact line deltas.

## Step 4: Execution Readiness Gating (P6.7)
* **Location:** `backend/core/scanner/execution_readiness.py`
* **Action:** The system aggregates the Replay Stability and Simulation Confidence into a master `execution_readiness_score`.
* **Output:** A Boolean-equivalent state (`EXECUTION_READY`, `LIMITED_READY`, `NOT_READY`). Only when this is green will future systems cross the mutation boundary.
