# Workspace Schema

## Orchestration Directory: `.orchestration/`

### 1. Retention Guarantees
- `p6/`, `p65/`, `p66/` subdirectories exist strictly on a per-run basis inside `workspaces/<workspace_id>/<run_id>/`.
- Data within these directories represents a frozen snapshot of cognition and MUST NOT be rewritten or purged after the run completes.

### 2. Folder Guarantees
- `p6/patches.json`: Contains the raw grounded mutation targets for the snapshot.
- `p65/replays.json`: Contains drift, collision, and relocation state tracking against the live file system.
- `p66/simulations.json`: Contains purely virtual string-injection diff summaries and syntax sanity results.

### 3. Readonly Guarantees
- At no point during P6, P6.5, or P6.6 may the orchestration engine invoke `fs.writeFile` against any file outside of `.orchestration/`.

### 4. Replay Guarantees
- Replays must be entirely localized to the run folder's perspective and should compute stability dynamically against the workspace's current state.
