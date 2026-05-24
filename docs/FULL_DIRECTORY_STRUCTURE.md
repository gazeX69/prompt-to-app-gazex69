C:\Users\gaze\Documents\cobacoba\ai-agent/
├── .env                          # Environment variables (DASHSCOPE_KEY, ports)
├── .gitignore                    # Comprehensive ignore rules
├── .git/
├── README.md                     # Main project documentation
├── LogAI.md                      # AI audit log (deep analysis of UI stuck bug)
├── ERROR_LOG.md                  # System error log (13 fixes documented)
├── WORKLOG.md                    # System work log (migration + stabilization)
├── LICENSE                       # MIT License
├── package-lock.json
├── requirements.txt              # Python dependencies for backend
├── append.py                     # Script that appended deep audit to LogAI.md
├── test_gen.py                   # Simple HTTP test for /generate endpoint
├── test_trigger.py               # Another trigger test for /generate
├── test_socket.py                # Socket.IO client test script
│
├── backend/                      # Python FastAPI orchestration backend
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point + lifespan + WS bridge
│   ├── requirements.txt          # Backend-specific requirements (binary/unreadable)
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py             # Pydantic Settings from .env
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic models: GenerateRequest, ExecuteRequest, etc.
│   ├── services/
│   │   ├── __init__.py
│   │   └── ai_service.py         # OpenAI/DashScope LLM client wrapper
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── generate.py           # POST /generate endpoint
│   │   └── execute.py            # POST /execute endpoint
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── project_orchestrator.py  # Main generation pipeline (6 stages)
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── tools.py              # Filesystem ops (write_file, append_file, etc.)
│   │   └── parser.py             # AI response parser (===FILE:=== protocol)
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── templates.py          # System prompts + user prompt builders
│   ├── sockets/
│   │   └── manager.py            # Socket.IO server + emit functions
│   ├── templates/
│   │   ├── registry.py           # Template scaffolding (copies template dir)
│   │   ├── generate_template.py  # Script that generates vite-react-ts template files
│   │   └── registry.py          # Points React/Vite scaffold to templates/react-vite-ts
│   │       ├── package.json
│   │       ├── vite.config.ts
│   │       ├── tsconfig.json
│   │       ├── tsconfig.node.json
│   │       ├── tailwind.config.js
│   │       ├── postcss.config.js
│   │       ├── index.html
│   │       └── src/
│   │           ├── main.tsx
│   │           ├── App.tsx
│   │           └── index.css
│   ├── memory/
│   │   ├── __init__.py
│   │   └── store.py              # In-memory project generation history
│   ├── runtime_client/
│   │   ├── __init__.py
│   │   └── client.py             # HTTP client for Node Runtime + SSE bridge
│   └── sandbox/ (MISSING!)
│       └── executor.py           # *** REFERENCED BUT DOES NOT EXIST ***
│
├── runtime/                      # Node.js Runtime Sandbox
│   ├── package.json
│   ├── ARCHITECTURE_MAP.md       # Ownership boundaries documentation
│   ├── PLAN.md                   # Phase 1 & 2 implementation plan
│   ├── WORKLOG.md
│   ├── ERROR_LOG.md
│   └── src/
│       ├── server.ts             # Express server: SSE, REST endpoints
│       ├── types/
│       │   └── events.ts         # RuntimeEventType enum + RuntimeEvent interface
│       ├── events/
│       │   └── RuntimeEventBus.ts # Event emitter (Node EventEmitter subclass)
│       ├── processes/
│       │   └── RuntimeProcessManager.ts  # execa-based process spawn/kill
│       ├── workspace/
│       │   └── WorkspaceManager.ts  # Workspace creation + governance files
│       ├── templates/
│       │   └── TemplateRegistry.ts   # Template scaffolding (vite-react-ts)
│       └── preview/
│           └── PreviewDetector.ts    # Health-check based port detection
│
├── frontend/                     # React + Vite IDE Shell
│   ├── package.json
│   ├── vite.config.ts
│   ├── README.md
│   └── src/
│       ├── main.tsx              # React entry: StrictMode + App
│       ├── App.tsx               # Root: initSocket on mount, cleanupSocket on unmount
│       ├── App.css               # Vite default styles (hero, counter, etc.)
│       ├── index.css             # Tailwind imports + custom scrollbar
│       ├── config/
│       │   ├── env.ts            # API_URL, WS_URL from env vars
│       │   └── runtime.ts        # Default config constants
│       ├── services/
│       │   ├── api.ts            # REST API client (fetch wrapper)
│       │   └── socket.ts         # Socket.IO client singleton
│       ├── sockets/
│       │   └── socketManager.ts  # Socket event handlers + init/cleanup
│       ├── stores/
│       │   ├── agent.store.ts    # Zustand store: AgentState, activities, logs
│       │   ├── terminal.store.ts # Terminal lines store
│       │   ├── preview.store.ts  # Preview URL store
│       │   ├── settings.store.ts # Theme settings store
│       │   └── workspace.store.ts # Active project store
│       ├── components/
│       │   ├── ErrorBoundary.tsx  # React error boundary with retry
│       │   └── StatusBar.tsx      # Bottom status bar showing agent state
│       ├── layouts/
│       │   └── WorkspaceLayout.tsx # Main layout: Sidebar + Main + Preview panels
│       ├── panels/
│       │   ├── MainWorkspace.tsx  # Vertical split: PromptWorkspace + TerminalPanel
│       │   ├── PromptWorkspace.tsx # Prompt input + Generate button + ProgressView
│       │   ├── ProgressView.tsx   # Stage progress + activity stream
│       │   ├── TerminalPanel.tsx   # Terminal log display
│       │   ├── PreviewPanel.tsx    # iframe preview + error state
│       │   └── SidebarPanel.tsx    # Icon sidebar navigation
│       ├── lib/
│       │   └── utils.ts           # cn() utility (clsx + tailwind-merge)
│       └── assets/
│           ├── vite.svg
│           ├── react.svg
│           └── hero.png
│
└── workspaces/                    # Generated applications (empty, gitignored)
