# AI Runtime Core Implementation Plan

## Phase 1: Foundation (Current)
- Initialize project structure and dependencies.
- Build Central Event Bus (`RuntimeEventBus`) for decoupled communication.
- Build Process Manager (`RuntimeProcessManager`) with Windows-first stability, using `node-pty`, `execa`, and `tree-kill`.
- Build WebSocket Telemetry (`WebSocketGateway`) for real-time `stdout`/`stderr` streaming without fake logs.
- Build Workspace System (`WorkspaceManager`) to scaffold directories and governance files.
- Build Template Engine (`TemplateRegistry`) to rapidly scaffold the `vite-react-ts` template.
- Build Preview Engine (`PreviewDetector`) to verify server readiness before emitting `PREVIEW_READY`.
- Benchmark test: Scaffold, install, start dev server, stream logs, attach preview successfully.

## Phase 2: AI Orchestration (Future)
- Implement File Generation Protocol (`GenerationProtocolParser`).
- Implement LLM Integration (`llm/providers`).
- Implement Repair Loop (`RepairEngine`) to catch build/command failures and retry.

## Critical Rules
- All communications MUST flow through the Event Bus.
- No direct UI state mutation in the frontend.
- Zero AI generation in Phase 1.
