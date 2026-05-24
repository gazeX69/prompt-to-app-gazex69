# RUNTIME BOUNDARIES

This document maps out what the backend orchestration engine is legally allowed to do to the file system.

## 1. Safe Readonly Operations
The following systems run freely and constantly:
- `workspace_scanner.py`: Full permission to traverse trees, extract symbols, and compute blast radius graphs.
- `patch_grounding.py`: Full permission to parse files, detect zones, and compute fuzzy offsets.
- `patch_simulation.py`: Full permission to copy file strings into memory and diff them.

## 2. Authorized Artifact Writes
The orchestration engine holds bounded write permissions specifically mapped to:
- `<project-root>/workspaces/<ws_id>/<run_id>/.orchestration/p6/`
- `<project-root>/workspaces/<ws_id>/<run_id>/.orchestration/p65/`
- `<project-root>/workspaces/<ws_id>/<run_id>/.orchestration/p66/`

## 3. Unsafe / Forbidden Write Pathways
The orchestration engine currently possesses **ZERO** pathways to mutate the primary user repository (`src/*`, `package.json`, etc.). 

If you are continuing this architecture into P11 (Controlled Mutation), you must build an explicit, highly guarded Python controller (`apply_patches.py`) that strictly consumes `simulations.json` and invokes Python file handling logic wrapped in a `try/except` rollback block. Do NOT use shell scripts (`bash -c "sed ..."`) to mutate source files.
