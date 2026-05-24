# FAILURE PATTERNS

This document serves as an institutional memory of historical engineering failures. Do NOT repeat these mistakes.

## 1. The Monolithic `.orchestration` Hydration Crash (P2.5)
* **Issue:** `GET /workspaces/{id}/artifacts` returned the entire content of every file inside `.orchestration` in a single JSON payload.
* **Symptom:** UI locked up instantly. Browser ran out of memory.
* **Root Cause:** Sending megabytes of string data to the React thread synchronously.
* **Solution:** Split hydration into index mapping (`GET /artifacts`) and lazy content loading (`GET /artifacts/{id}`). Keep payload sizes tiny.

## 2. The `backend/workspaces/` Illusion (P2)
* **Issue:** Early development accidentally created `backend/workspaces/` to mirror `root/workspaces/`.
* **Symptom:** Patches were being analyzed on stale backend copies while the user preview rendered the root workspace.
* **Root Cause:** Path assumptions in Python.
* **Solution:** Ensure the backend scans `<project-root>/workspaces/` directly. Never copy source code purely for backend parsing.

## 3. Regex Bracket Imbalance (P4)
* **Issue:** The regex finding region blocks like `useEffect` would capture trailing text or miss nested objects.
* **Symptom:** Blast radius cognition returned bizarre, truncated target strings.
* **Root Cause:** Regex cannot natively handle arbitrary recursion depths without incredibly complex lookarounds.
* **Solution:** Implemented the `run_syntax_sanity` bracket balancing logic in `P6.6` to strictly veto any regex operation that accidentally leaves open braces.

## 4. Duplicate Injection Collapse (P6.5)
* **Issue:** The system would try to append an import statement that a previous run had already successfully appended.
* **Symptom:** `import { FileCode } from "lucide-react"` appearing 5 times in a row.
* **Root Cause:** The patch grounding logic was stateless against previous runs.
* **Solution:** Added `duplicate_injection_detected` logic to `evaluate_patch_replay` in P6.5 to dynamically cross-reference the target patch content with the live file strings before appending.

## 5. React/Vite Ecosystem Contract Drift (P6.8)
* **Issue:** React/Vite scaffold generation and LLM feature output could overwrite ecosystem contract files.
* **Symptom:** Builds failed with TypeScript project-reference errors, invalid Vite config, missing entrypoints, or blank previews.
* **Root Cause:** `package.json`, `tsconfig*.json`, `vite.config.ts`, `index.html`, and React entrypoints were not protected as a single ecosystem contract.
* **Solution:** Added the canonical template at `templates/react-vite-ts/`, blocked feature output from overwriting contract files, and validated the environment before install/build.

## 6. TS6310 Repair Loop (P6.8)
* **Issue:** TypeScript project references could be generated in an invalid build shape.
* **Symptom:** Repeated repair attempts reintroduced or failed to resolve TS6310-shaped errors.
* **Root Cause:** The repair loop delegated TypeScript config recovery to generalized LLM repair instead of restoring a known-good config.
* **Solution:** Classified the failure as `tsconfig_reference_invalid` / `E_TS_REFERENCE_INVALID` and restored canonical TypeScript config in a deterministic repair pass.

## 7. Duplicate Template Authority (P6.9)
* **Issue:** Backend and runtime template registries carried separate React/Vite assumptions.
* **Symptom:** A future edit could update one template path while leaving another stale.
* **Root Cause:** Template source and registry metadata were duplicated.
* **Solution:** Consolidated React/Vite template authority to `templates/react-vite-ts/` and removed legacy duplicated `backend/templates/vite-react-ts/` config files.

## 8. Informal Runtime State Drift (P6.9)
* **Issue:** Backend and frontend used implicit or lowercase execution state strings.
* **Symptom:** UI state, telemetry, and future verifiers could disagree about whether a run was validating, repairing, preview-ready, failed, or complete.
* **Root Cause:** No shared machine-readable execution state model existed.
* **Solution:** Added shared canonical execution states through `frontend/src/runtime/execution_contract.json`, loaded by both frontend and backend.

## 9. Runtime Error String Drift (P6.9)
* **Issue:** Error classification was string-oriented and inconsistent.
* **Symptom:** Repair and telemetry could describe the same failure with different labels.
* **Root Cause:** There was no focused React/Vite error taxonomy.
* **Solution:** Added structured error codes including `E_TS_REFERENCE_INVALID`, `E_IMPORT_RESOLUTION`, `E_VITE_CONFIG`, `E_REACT_ROOT_MISSING`, `E_RUNTIME_BLANK`, `E_DEPENDENCY_MISSING`, `E_BUILD_FAILURE`, and `E_PREVIEW_UNREACHABLE`.

## 10. Blank Preview False Positive (P6.8/P6.9)
* **Issue:** A dev server could be reachable while the rendered React application was missing or blank.
* **Symptom:** Runtime appeared successful even though `#root` was empty or the body had no meaningful content.
* **Root Cause:** Preview readiness was treated as server availability rather than DOM verification.
* **Solution:** Runtime verification now checks preview reachability, `#root` existence, rendered React content inside `#root`, non-blank body, and fatal console/page errors.

## 11. Workspace Merge Scaffold Drift (P6.9)

* **Issue:** Workspace scaffolding merged template files into existing run directories.
* **Symptom:** Old `package.json`, `tsconfig`, and ecosystem artifacts survived across runs, causing nondeterministic React/Vite behavior and recurring TS6310 failures even after stabilization patches.
* **Root Cause:** `shutil.copytree(..., dirs_exist_ok=True)` allowed stale workspace state to survive between runs instead of creating a fresh isolated scaffold.
* **Solution:** Enforced hard-reset workspace scaffolding. Existing run directories are removed before template copy so every orchestration run starts from a deterministic canonical template state.
