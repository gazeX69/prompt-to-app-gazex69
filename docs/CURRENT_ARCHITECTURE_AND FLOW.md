┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React 19 + Vite)               │
│  Port 5173                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  WorkspaceLayout                                         │   │
│  │  ├─ SidebarPanel (icons)                                 │   │
│  │  ├─ MainWorkspace                                        │   │
│  │  │  ├─ PromptWorkspace (input + ProgressView)            │   │
│  │  │  └─ TerminalPanel (log output)                        │   │
│  │  └─ PreviewPanel (iframe)                                │   │
│  │                                                          │   │
│  │  Stores (Zustand): agent, terminal, preview, settings,   │   │
│  │  workspace                                                │   │
│  │  Services: api.ts (REST), socket.ts (Socket.IO client)   │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │              │                                        │
│         │ REST          │ WebSocket (Socket.IO)                 │
└─────────┼──────────────┼────────────────────────────────────────┘
          │              │
          ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (Python FastAPI)                      │
│  Port 8000                                                       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  main.py                                                 │   │
│  │  ├─ FastAPI app with lifespan                            │   │
│  │  ├─ CORS middleware                                      │   │
│  │  ├─ Socket.IO ASGI wrapper                               │   │
│  │  ├─ Routes: /generate, /execute, /health                 │   │
│  │  └─ _bridge_runtime_event() (SSE->Socket.IO bridge)      │   │
│  │                                                          │   │
│  │  Routes:                                                 │   │
│  │  ├─ generate.py → triggers orchestrator in background    │   │
│  │  └─ execute.py → commands via executor (MISSING)         │   │
│  │                                                          │   │
│  │  Orchestrator:                                           │   │
│  │  └─ project_orchestrator.py (6-step pipeline)            │   │
│  │                                                          │   │
│  │  Services:                                               │   │
│  │  └─ ai_service.py (Qwen/DashScope LLM via OpenAI SDK)    │   │
│  │                                                          │   │
│  │  Runtime Client:                                         │   │
│  │  └─ client.py (HTTP + SSE consumer from Node Runtime)    │   │
│  │                                                          │   │
│  │  Sockets:                                                │   │
│  │  └─ manager.py (Socket.IO server + emit functions)       │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                                                      │
│         │ HTTP REST + SSE (Server-Sent Events)                 │
└─────────┼──────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RUNTIME (Node.js Express)                     │
│  Port 3001                                                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  server.ts                                               │   │
│  │  ├─ GET  /runtime/events (SSE stream)                   │   │
│  │  ├─ POST /runtime/workspace/create                      │   │
│  │  ├─ POST /runtime/command/run                           │   │
│  │  ├─ POST /runtime/dev/start                             │   │
│  │  ├─ POST /runtime/dev/stop                              │   │
│  │  ├─ GET  /runtime/processes                             │   │
│  │  └─ GET  /runtime/health                                │   │
│  │                                                         │   │
│  │  Components:                                            │   │
│  │  ├─ RuntimeProcessManager (execa subprocesses)          │   │
│  │  ├─ WorkspaceManager (dir + governance files)           │   │
│  │  ├─ TemplateRegistry (scaffold vite-react-ts)           │   │
│  │  ├─ PreviewDetector (port health-check)                 │   │
│  │  └─ RuntimeEventBus (EventEmitter)                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Generates and manages:                                         │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   workspaces/         │  Generated Vite React apps
        │   (project-001/)      │
        └──────────────────────┘