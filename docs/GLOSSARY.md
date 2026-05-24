# GLOSSARY

Ensure you strictly abide by these terms when documenting or extending logic.

- **Blast Radius**: A numeric indicator evaluating how heavily a specific file influences the broader workspace (e.g., modifying `utils.ts` has a higher blast radius than `Button.tsx`).
- **Grounding**: The process of taking a vague AI intent (e.g., "add this import") and mapping it to absolute line numbers in the target file.
- **Drift**: When the target file is manually modified by a human or a previous agent run, causing the `Grounding` coordinates to become stale.
- **Fuzzy Relocation**: The backend's ability to heuristically shift grounded line coordinates up or down to compensate for Drift.
- **Replay Validation**: Checking if a historic or pending patch is still structurally safe to execute against the live file.
- **Simulation**: In-memory string manipulation to predict exactly what the patched file will look like without touching the hard drive.
- **Syntax Sanity**: A lightweight check ensuring braces `{}` and brackets `[]` are perfectly balanced after Simulation.
- **Execution Readiness**: The final boolean state aggregating Replay and Simulation metrics to authorize real filesystem mutation.
