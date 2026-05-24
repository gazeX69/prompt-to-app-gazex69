Create a compact architectural continuity document for the current AI Agent state.

DO NOT perform new implementation.

Generate:
docs/P7_STATE_CONTINUITY.md

Requirements:

* concise but complete
* optimized for future context restoration
* avoid long essays
* preserve architectural direction and current priorities

Must include:

1. Current Product Direction

* preview-first AI coding UX
* mode-based workspace
* orchestration internals hidden by default
* product goal comparable to Codex/Cursor workflow simplicity

2. Completed Phases

* runtime stabilization phases
* structured runtime errors
* runtime lifecycle event bus
* runtime state machine
* crash-proof UI containment
* navigation refactor

3. Current UX Architecture

* Generate mode
* Preview mode
* Source mode
* Runtime mode
* History mode

4. Known Problems

* workspace preview ownership still incomplete
* preview/runtime session persistence unfinished
* runtime restart actions incomplete
* history UX still transitional

5. Immediate Next Priority
   P7.2 Phase 2:
   Workspace Preview Binding

Include:

* root cause
* intended ownership model
* validation expectations

6. Critical Design Rules

* preview is primary product surface
* avoid engineering-dashboard UX
* hide orchestration complexity
* avoid triple-split layout return
* preserve runtime stabilization foundation

7. Important Runtime Constraints

* do not rewrite orchestration
* additive architecture only
* preserve structured runtime lifecycle system

Keep the document highly compressed and implementation-oriented.
