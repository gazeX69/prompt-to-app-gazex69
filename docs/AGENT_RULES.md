# AGENT RULES

As an autonomous AI operating this codebase, you must adhere to the following rigid operational rules.

## 1. Safety Before Mutation
You MUST NOT execute destructive actions (`rm -rf`, raw file overwrites, blind patch applications) without first validating the execution readiness matrix. Read the output of `GET /workspaces/{id}/readiness`. If the status is `NOT_READY`, you are forbidden from invoking filesystem writes.

## 2. No Framework Hype
Avoid injecting unnecessary libraries. Use Vanilla CSS, Zustand, and standard React hooks before reaching for Tailwind, Redux, or heavy UI component libraries unless explicitly mandated by the user.

## 3. Engineering Density over Flash
When modifying the UI (`frontend/src/panels/`), maintain the existing "Codex-style" aesthetic:
- Dense text.
- Monospaced typography for variables and metrics.
- Subdued backgrounds (`#1e1e1e`, `#252526`).
- Subtle accent colors (red/green/yellow for status indicators).
- No distracting animations or giant padding blocks.

## 4. Bounded Regex over Heavyweight AST
When extending code intelligence (`backend/core/scanner/`), prefer high-speed heuristics via regular expressions over installing Babel, Esprima, or Tree-sitter. We prioritize sub-second cross-repository analysis speed over perfect lexical precision.

## 5. Artifact Documentation Protocol
Whenever you complete an architectural shift, you must update the `workspace_schema.md` and `mutation_contracts.md` files. State must remain perfectly documented.
