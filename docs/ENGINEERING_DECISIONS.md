# ENGINEERING DECISIONS

Understanding *why* we built things this way is more important than knowing *what* we built.

## 1. Why Readonly First?
We spent 7 engineering phases building observation, drift detection, and simulation without writing a single line of actual code into the workspace. Why? 
Because AI agents are non-deterministic. If you give an AI raw execution access to a filesystem before it possesses a robust "sanity check" boundary, it will quietly corrupt files. By forcing all intents through a dense, visual pipeline (`FileInspector`), the human supervisor can instantly visually verify the system's reasoning before catastrophic damage occurs.

## 2. Why Regex instead of Babel/AST?
AST parsers are heavy, slow, and often crash on malformed JSX or partial code states. We are building an intelligence layer that must scan hundreds of files per second and tolerate horribly broken AI-generated code. Regex, while fragile, is significantly faster, completely dependency-free, and handles broken syntax gracefully.

## 3. Why the Dense Codex-Style UI?
We do not want a glossy SaaS dashboard. We want a terminal-oriented cockpit. The goal is to maximize the speed at which an engineer can ingest telemetry, dependency maps, and blast radius calculations. Animations are distracting. Dense, monospaced text is efficient.

## 4. Why does `.orchestration` live inside the workspace?
By placing `.orchestration/` artifacts directly inside the target workspace (rather than inside the backend container), the run snapshots travel naturally with the source code. If a user downloads the workspace ZIP, they download the AI's entire operational memory context along with it.

## 5. Why is React/Vite template authority singular?
React/Vite execution previously allowed ecosystem contract drift between generated files, backend template assumptions, and runtime template assumptions. The canonical source is now `templates/react-vite-ts/`. Backend and TypeScript runtime registries reference that source instead of carrying duplicate copies of `package.json`, `tsconfig*.json`, `vite.config.ts`, `index.html`, or React entrypoint assumptions.

## 6. Why protect ecosystem contract files?
The React/Vite runtime depends on a small set of configuration files staying internally consistent. LLM-generated feature output is not allowed to overwrite:
- `package.json`
- `tsconfig.json`
- `tsconfig.app.json`
- `tsconfig.node.json`
- `vite.config.ts`
- `index.html`
- `src/main.tsx`

Known TypeScript and Vite configuration failures are repaired by restoring canonical config, not by asking the LLM to improvise. This prevents TS6310-shaped loops and keeps repair passes deterministic.

## 7. Why formalize runtime states before P7?
P7 will need trustworthy execution telemetry. Runtime states are now defined through a shared contract rather than ad hoc strings. Backend and frontend use the same canonical state names for validation, install, build, preview startup, verification, repair, failure, and completion.

## 8. Why use structured runtime error codes?
String-oriented error classification caused repair and telemetry drift. React/Vite failures now use focused machine-readable codes such as `E_TS_REFERENCE_INVALID`, `E_IMPORT_RESOLUTION`, `E_VITE_CONFIG`, `E_REACT_ROOT_MISSING`, `E_RUNTIME_BLANK`, `E_DEPENDENCY_MISSING`, `E_BUILD_FAILURE`, and `E_PREVIEW_UNREACHABLE`.

## 9. Why not auto-install undeclared imports yet?
Automatic package installation would expand the runtime dependency surface before a policy exists to govern it. P6.9 introduces a minimal dependency policy foundation that can classify allowed, blocked, and undeclared imports, but it intentionally does not install packages from LLM output.
