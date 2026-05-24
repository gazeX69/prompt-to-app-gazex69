# Engineering Freeze Constraints

## P6.7 Core Constitution

### 1. Forbidden Architectural Changes
- The underlying AI Planner must not output direct file diffs. It must output structural intentions that the system grounds via `patch_grounding.py`.
- No new persistent data stores or vector databases may be introduced to replace the filesystem-as-truth orchestration boundary.
- The `FileInspector` must remain readonly. No Monaco code editors or inline patching forms are allowed in the observability shell.

### 2. Mutation Boundaries
- Live files may only be altered if a patch transitions safely through: `Patch Synthesized -> Grounded -> Replay Verified -> Simulated -> Sanity Checked`.
- Under no circumstances may an orchestrator write a full generated file over an existing user file without validating symbol continuity.

### 3. Orchestration Invariants
- The system must treat `<project-root>/workspaces/` as the single source of truth.
- Backend APIs must never cache workspace file structures in global memory across requests.

### 4. Execution Safety Guarantees
- If a duplicate injection is flagged during `P6.5 Replay Validation`, the execution layer MUST drop the patch.
- If syntax sanity fails during `P6.6 Simulation`, the execution layer MUST drop the patch.
