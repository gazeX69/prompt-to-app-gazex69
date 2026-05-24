# AI AUDIT LOG

## A. Audit Metadata
- **Date**: 2026-05-22
- **Runtime Environment**: Local Development
- **OS**: Windows
- **Node version**: v25.9.0
- **Python version**: 3.14.4
- **Package manager**: npm / pip
- **Build mode**: Development

---

## B. Initial Architecture Understanding

Ringkasan:
- **Frontend Role**: React/Vite UI shell. Bertanggung jawab murni pada rendering state dan UI (tidak ada orchestration logic). Berkomunikasi dengan backend via REST dan WebSockets.
- **Backend Role**: Central AI Core berbasis Python. Mengontrol state orchestration, prompt template, call ke AI provider, dan WebSocket lifecycle yang menghubungkan frontend dan runtime.
- **Runtime Role**: Node.js Sandbox Executor. Berfungsi sebagai "dumb daemon" untuk mengeksekusi shell commands (`npm install`, `npm run dev`) secara aman, memonitor port, dan stream terminal log ke backend.
- **Orchestration Role**: Dipegang penuh oleh Python backend yang mengatur loop Generate -> Parse -> Write -> Install -> Build -> Auto-Repair.
- **Websocket Role**: Penghubung real-time log dan event antara Frontend, Backend, dan Runtime. Frontend terhubung ke Backend (Python), sementara Runtime stream output ke Backend menggunakan Server-Sent Events (SSE).
- **Provider Role**: Diabstraksi oleh layer services pada Python backend (seperti DashScope/OpenAI wrapper) untuk mengeksekusi prompt LLM.

---

## C. Startup Procedure

Langkah nyata menjalankan aplikasi:
1. **Runtime Startup**:
   - Command: `npm start` (di dalam folder `runtime`)
   - Hasil: Berhasil.
   - Output: `Node Runtime Sandbox listening on port 3001`
   - Health Endpoint HTTP 200 OK (`http://127.0.0.1:3001/runtime/health`).
2. **Frontend Startup**:
   - Command: `npm run dev` (di dalam folder `frontend`)
   - Hasil: Berhasil.
   - Output: `VITE v8.0.14 ready in 818 ms. Local: http://localhost:5173/`
   - Port yang digunakan: 5173.
3. **Backend Startup**:
   - Command: `venv\Scripts\python main.py` (di dalam folder `backend`)
   - Hasil: GAGAL (Crash on startup).
   - Output: `ModuleNotFoundError: No module named 'dotenv'`
   - Catatan: Menjalankan `pip install -r requirements.txt` menunjukkan semua packages terinstall, namun `python-dotenv` tidak tercatat di dalam `requirements.txt` sehingga gagal di-import.

---

## D. Runtime Flow Observation

Jelaskan:
- **Flow aplikasi terputus (Blocked)** sejak startup.
- **Backend Offline**: Karena backend tidak bisa dijalankan (crash), alur orchestration, websocket bridge, dan komunikasi AI tidak pernah dimulai.
- **Frontend UI**: Frontend berhasil hidup dan menyajikan file HTML, namun dipastikan akan menampilkan indikator offline ("Cannot connect to AI Core" / White screen) karena tidak bisa membuka koneksi ke port backend.
- **Runtime Sandbox**: Runtime daemon berjalan normal di background, tapi berada di idle state karena tidak menerima HTTP command (seperti `/runtime/command/run`) dari backend.

---

## E. User Journey Simulation

Simulasi:
- **Membuka aplikasi**: User mengakses `http://localhost:5173`. Halaman HTML berhasil diload oleh browser.
- **Koneksi Backend**: Applikasi React mencoba membuka WebSocket ke Python Backend. Karena backend mati, koneksi timeout/refused.
- **Response UX**: UI memberikan error state atau freeze loading screen sesuai behavior default saat backend down.
- **Melakukan request AI**: Tidak dapat dilakukan (tombol disable atau fail silent) karena orchestration logic mati.
- **Kesimpulan UX**: Blocker kritis ("Dead on Arrival") akibat backend crash. User tidak bisa mencapai tahap request AI maupun melihat log terminal.

---

## F. Error Log

### Error #1
- **Timestamp**: 2026-05-22T16:01:11Z
- **Location**: `backend/main.py`, baris ke-7
- **Severity**: CRITICAL / FATAL
- **Reproduction Steps**: Eksekusi perintah `python main.py` di dalam directory `backend` (meskipun environment `requirements.txt` telah ter-install sempurna).
- **Console Output**:
  ```python
  Traceback (most recent call last):
    File "C:\Users\gaze\Documents\cobacoba\ai-agent\backend\main.py", line 7, in <module>
      from dotenv import load_dotenv
  ModuleNotFoundError: No module named 'dotenv'
  ```
- **Probable Cause**: Module `python-dotenv` digunakan di dalam source code backend (`main.py`), tetapi belum didaftarkan di `requirements.txt`.
- **Related Modules**: `backend/main.py`, Backend initialization flow.
- **Recovery Behavior**: Tidak ada. Process langsung terminate.

---

## G. Stability Assessment

- **Frontend Stability**: MEDIUM (Berhasil hidup, namun bergantung penuh pada backend untuk state management).
- **Backend Stability**: LOW (Crash on startup, Fatal Blocker).
- **Runtime Stability**: HIGH (Berdiri independen, health endpoint stabil, API siap menerima command).
- **Websocket Stability**: LOW (Gagal terbentuk akibat backend down).
- **Orchestration Stability**: LOW (Tidak dapat diukur karena backend tidak dapat start).
- **Provider Stability**: LOW (Tidak dapat diukur karena service belum terinisialisasi).

---

## H. Dangerous Zones Observed

Catatan dari observasi dan dokumentasi map:
- **Missing Dependency Risk**: Kesalahan pada `requirements.txt` menyebabkan sistem mati total dan merusak development flow.
- **Central Point of Failure**: Seluruh arsitektur terlalu bergantung pada Python Backend (sebagai Orchestrator sekaligus Websocket Gateway). Jika backend jatuh, baik frontend maupun runtime menjadi useless.
- **Orchestration Bottleneck**: Seperti disebutkan di dokumen `AI_ROUTE_SYSTEM_MAP.md` dan `DEPENDENCY_RELATION_MAP.md`, arsitektur saat ini mengikat kuat (tightly coupled) proses antara AI Provider, Websocket, dan Node Runtime ke dalam satu central Python layer.
- **Architecture Drift Risk**: Terdapat mismatch kontrak antara sistem yang berjalan (Python-centric) dan dokumen sistem yang merencanakan Typescript `AIRoute` layer.

---

## I. Real Runtime Dependency Chain

Flow dependensi NYATA saat ini (karena failure):
- User Browser -> `Frontend (localhost:5173)` [STATUS: Alive, Waiting]
- Frontend -> (Gagal koneksi Websocket) -> `Backend (localhost:8000/main.py)` [STATUS: Dead, Dependency Error]
- Backend -> (Terputus) -> `Runtime (localhost:3001)` [STATUS: Alive, Idle]

Arsitektur tidak dapat merangkai chain dari frontend hingga ke eksekusi sandbox akibat blocker di tengah layer.

---

## J. Final Audit Conclusion

- **Kondisi Project**: Blocker/Broken di sisi backend. Project tidak bisa digunakan oleh user dalam state saat ini.
- **Layak Development Lanjut?**: Ya, namun ada tech debt mendesak untuk menyelesaikan basic startup dependency sebelum melangkah ke AI feature development.
- **Architecture Stability**: Cukup stabil di layer Frontend dan Runtime, namun rapuh di sisi Backend.
- **Area Paling Rawan**: Python Backend Orchestration (khususnya initialization cycle).
- **Area Paling Matang**: Runtime Node.js Sandbox (health endpoint responsif dan terisolasi dengan baik).
- **Blocker Terbesar**: Module `dotenv` hilang di environment backend, menyebabkan entire system down.
- **Technical Debt Terbesar**: Mismatch arsitektur antara Python backend code base dengan `AIRoute` plan document, serta dependensi package yang tidak sinkron.


# Deep Audit: UI Stuck During Generation

## A. Audit Date
2026-05-22

## B. Test Matrix

| Test | Generated App Actually Runs? | UI Stage Stuck? | Preview Works? | Error Visible in UI? | Backend Error? | Runtime Error? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TEST 1 (Counter)** | YES | YES (Feature Generation) | YES | NO | NO | NO (Idle) |
| **TEST 2 (Todo)** | YES | YES (Feature Generation) | YES | NO | NO | NO (Idle) |
| **TEST 3 (Calendar)**| NO (Build Failed) | YES (Feature Generation) | NO | NO | YES (Logged to file) | NO (Idle) |

## C. Observed Behavior
- Pada generate app sederhana (Test 1 & 2), backend **berhasil** mengeksekusi full pipeline (planning -> scaffolding -> writing -> install -> build -> dev server). Preview URL berhasil dibuat, dan aplikasi berjalan di background.
- Namun, **UI terputus total** dari realita. Activity stream tetap "Waiting for events...", dan Execution log tetap "Waiting for command...". Status progress bar tersangkut (stuck) pada stage optimistik "Feature Generation" yang di-set lokal oleh frontend.
- Pada Test 3 (Calendar), AI menghasilkan kode yang kompleks sehingga npm build gagal. Backend secara internal mendeteksi error, melakukan auto-repair loop, dan akhirnya mencatat error ke `ERROR_LOG.md`. Namun lagi-lagi, UI tidak berubah menjadi "Failed" dan tetap stuck di "Feature Generation".

## D. Event Pipeline Map

Flow yang seharusnya:
Backend Orchestrator → Backend Socket Emit (`manager.py`) → Socket.IO Transport (`ASGIApp`) → Frontend Socket Listener (`socketManager.ts`) → Agent Store (`zustand`) → UI Progress Component

Flow Aktual (Terputus di ujung frontend):
Backend Orchestrator → Backend Socket Emit [BERHASIL]
Socket.IO Transport → Network [BERHASIL]
Frontend Socket Listener → [MATI/DISCONNECTED] → Store tidak pernah ter-update.

## E. Root Cause Findings

### Finding #1
- **Title**: React Strict Mode Socket Disconnection (The Main Blocker)
- **Severity**: CRITICAL
- **Evidence**: 
  - `frontend/src/App.tsx` memanggil `useEffect(() => { return () => cleanupSocket() }, [])`.
  - `frontend/src/main.tsx` membungkus App dengan `<StrictMode>`.
  - `frontend/src/sockets/socketManager.ts` menginisialisasi socket pada module level, namun `cleanupSocket()` memutuskan koneksi (`socketService.disconnect()`) dan tidak ada fungsi remount/reconnect di `App.tsx`.
- **Affected Files**: `frontend/src/App.tsx`, `frontend/src/sockets/socketManager.ts`.
- **Why UI Gets Stuck**: Strict Mode me-mount, lalu unmount (memicu cleanup dan disconnect socket permanen), dan me-mount ulang App tanpa menyalakan socket lagi. Akibatnya UI menjadi "tuli" terhadap semua event (termasuk stage updates, terminal stream, dan failure event) dari backend.
- **Reproducibility**: 100% konsisten di semua skenario.
- **Suggested Fix Direction**: Pindahkan inisialisasi dan koneksi socket ke dalam body `useEffect` pada root component atau ke dalam hook store, agar koneksi di-reestablish setiap kali mount terjadi.

### Finding #2
- **Title**: Architecture Drift - Bypassing Node Runtime Sandbox
- **Severity**: MEDIUM
- **Evidence**: 
  - `backend/orchestrator/project_orchestrator.py` tidak menggunakan `runtime_client.run_command`.
  - Sebaliknya, ia mengimport `stream_command_async` dari `backend/sandbox/executor.py` yang menggunakan `asyncio.create_subprocess_exec` (Python native subprocess).
- **Affected Files**: `backend/orchestrator/project_orchestrator.py`, `backend/sandbox/executor.py`.
- **Why UI Gets Stuck**: Walaupun bukan penyebab utama stuck-nya state UI (karena executor.py tetap mengirim event socket), ini menjelaskan mengapa proses isolasi Node Sandbox diabaikan. Sandbox yang berjalan di port 3001 menjadi *useless daemon* karena orchestrator mengeksekusi shell secara mandiri.
- **Reproducibility**: 100%.
- **Suggested Fix Direction**: Ganti import di orchestrator untuk memanggil REST endpoint dari `RuntimeClient` dan mengandalkan event stream jembatan (yang sudah disiapkan di `main.py`).

## F. Execution Path Finding

- **Fakta Nyata**: Eksekusi benar-benar lewat **Python subprocess**, bukan Node Runtime Sandbox.
- **Kenapa execution log tetap “Waiting for command...”**: Walaupun Python subprocess memancarkan event `emit_terminal_line`, event ini tertahan dan dibuang oleh frontend yang berada dalam kondisi terputus (disconnected) akibat Finding #1.

## G. Error Propagation Finding

- **Kenapa error calendar tidak tampil jelas di UI?**: 
  Backend meng-catch exception dan mengirim event via `await emit_agent_state("failed", req.project_id)` serta menulis ke `ERROR_LOG.md`. 
  Namun karena koneksi websocket di frontend terputus permanen sejak aplikasi pertama kali dimuat, event `failed` ini tidak pernah sampai ke store `AgentState`. Akibatnya, UI tetap asyik berputar di status `Generating...`.

## H. Final Diagnosis

- **Penyebab Utama Stuck**: Bug pada lifecycle React `useEffect` (Frontend) dipadukan dengan Strict Mode yang menyebabkan Socket.IO memutuskan koneksi secara permanen setelah initial load.
- **Penyebab Tambahan**: Architecture drift di mana Python mengeksekusi langsung tanpa menyentuh Node Sandbox, berlawanan dengan dokumen `ARCHITECTURE_MAP.md`.
- **Area Fix Prioritas**: `frontend/src/App.tsx` dan `socketManager.ts`.
- **Estimasi Kompleksitas Fix**: Sangat Rendah (Low Complexity) - hanya perlu memindahkan logika `.connect()` dan `setupListeners()` ke dalam `useEffect` mounting phase.
- **Kategori**: Ini adalah **Bug Frontend (Websocket Lifecycle)**.

## I. Recommended Next Prompt

> "Berdasarkan LogAI.md, tolong perbaiki bug lifecycle WebSocket di frontend. Pindahkan inisialisasi socket (`connect()` dan `setupListeners()`) ke dalam `useEffect` di `App.tsx` atau sejenisnya, pastikan cleanup bekerja bersih, dan pastikan socket berhasil reconnect setelah Strict Mode unmount. Jangan sentuh backend orchestration dulu."

# Runtime Audit � Skill Pipeline Failure

## Timestamp
2026-05-23T09:24:42+07:00

## Summary
Both PHP and React generation fail during the terminal execution phase (Dev Server and Install, respectively). The failure is silent because the actual exception (NotImplementedError) has an empty string representation (""), causing the backend to default to unhelpful generic error messages.

## Test Environment
- OS: Windows
- Python: 3.10.x (Running uvicorn)
- Node: v25.9.0
- npm: 11.12.1
- PHP: 8.3.30
- Backend URL: http://127.0.0.1:8000
- Frontend URL: http://localhost:5173

## PHP Test Result
- Prompt: buat login sederhana dengan php
- Selected skill: php-basic
- Generated workspace: workspaces/php-audit-test
- Files generated: index.php, dashboard.php, logout.php, style.css, plus governance files
- Command: php -S 127.0.0.1:3000
- CWD: C:\Users\gaze\Documents\cobacoba\ai-agent\workspaces\php-audit-test
- Exit code / readiness: -1 (Failed to start process)
- Preview URL: None (crashed before detection)
- Frontend iframe URL: N/A (crashed before preview ready)
- Error observed: "Dev server failed" logged in ERROR_LOG.md. The underlying error is NotImplementedError thrown by syncio.create_subprocess_exec on SelectorEventLoop.

## React/Vite Test Result
- Prompt: buat todo app react
- Selected skill: react-vite
- Generated workspace: workspaces/react-audit-test
- Files generated: React source code files (App.tsx, main.tsx, etc.)
- Command: npm install --no-progress
- CWD: C:\Users\gaze\Documents\cobacoba\ai-agent\workspaces\react-audit-test
- Exit code: -1 (Failed to start process)
- npm stdout: (empty)
- npm stderr: (empty)
- Error observed: "Install failed" logged in ERROR_LOG.md. The underlying error is NotImplementedError thrown by syncio.create_subprocess_exec.

## Root Cause Candidates
Ranked list:
1. uvicorn overriding the ProactorEventLoop with SelectorEventLoop on Windows, which lacks subprocess support.
2. NotImplementedError stringifying to "", causing the executor to drop the real error and fall back to "Install failed".
3. main.py applying syncio.set_event_loop_policy too late or being overridden by the uvicorn startup routine.

## Confirmed Root Cause
The backend server running via uvicorn uses SelectorEventLoop on Windows. syncio.create_subprocess_exec does not support subprocesses on SelectorEventLoop and raises NotImplementedError. The stream_command_array_async function catches this as Exception and returns ExecuteResponse with error=str(e). Since str(NotImplementedError()) is "", error is empty. The orchestrator sees success=False and empty error, defaulting to generic strings like "Install failed" or "Dev server failed".

## Minimal Fix Plan
1. Fix the event loop policy in the uvicorn launch sequence or switch to syncio.run explicitly with Proactor event loop. (e.g. configuring uvicorn to use syncio loop explicitly instead of uto or wrapping it).
2. Fix ackend/sandbox/executor.py exception handling to use epr(e) instead of str(e) so exceptions with empty string representations (like NotImplementedError or CancelledError) are actually logged properly.

## Do Not Touch
- ackend/core/skills/builtin/php_basic.py
- ackend/core/skills/builtin/react_vite.py
- Frontend components (UI/styling)
- Laravel or other framework integrations

# SYSTEM AUDIT

## Area
Artifact Explorer & Workspace Synchronization

## Symptoms
* Artifact caching might become stale if `activeRunId` changes but file paths in `artifactSnapshots` remain the same base64 encoded paths.
* `get_run_dir` resolves the `latest` run by falling back to sorting `run_*` directories by `st_mtime`. If a past run is modified, it unexpectedly becomes the "latest", causing a race condition or stale workspace reference.
* `get_workspace_artifact_content` reads up to 5MB and sets `truncated = True`, but there's no continuous sync or partial read for growing files.
* Base64 encoding paths for `artifact_id` means files moved/renamed lose their identity.

## Root Cause Hypothesis
* Workspace metadata and "latest" resolution lack a definitive `state.json` or atomic symlink update, relying on filesystem timestamps (`st_mtime`) which are easily polluted.
* Frontend relies on a static fetch of `artifactSnapshots` that doesn't subscribe to file tree changes, leading to hydration mismatch if the backend mutates the orchestration files.

## Evidence
* `backend/core/scanner/workspace_scanner.py`: `run_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)` is the fallback for `latest`.
* `frontend/src/stores/workspace.store.ts`: `artifactSnapshots` is loaded once during `loadWorkspaceData` and `loadRunData`.

## Risk Level
MEDIUM

## Recommended Stabilization
* Use a definitive `run_metadata.json` or an explicit database record to track the `latest` run, avoiding `st_mtime` sorting.
* Implement a WebSocket event for file tree changes so `ArtifactExplorer` can re-hydrate dynamically instead of on initial load only.

## Constraints
* preserve current architecture
* no major refactor
* no subsystem rewrite

## Codex Repair Task
Create a `run_index.json` or update SQLite DB to store the absolute latest run instead of relying on `st_mtime` fallback in `workspace_scanner.py`.

---

# SYSTEM AUDIT

## Area
Runtime Preview Stability

## Symptoms
* Single concurrency limit per project. Previewing an old run forcibly kills any currently running dev server for that project, even if they belong to different runs.
* Port allocation loops over 3000-3100 iteratively. It detects process collision, but a crash during startup might leave orphan processes.
* The frontend forces iframe reload by appending `&t=Date.now()`, which drops the entire DOM state even if the dev server was just HMR reloading.

## Root Cause Hypothesis
* `_runtime_registry` in `executor.py` uses `server_key = project_id` rather than `f"{project_id}_{run_id}"`. This forcibly evicts any prior run's runtime for the same project.
* The iframe URL in `PreviewPanel.tsx` forcefully invalidates cache using `Date.now()` on every render when `url` or `runId` changes, which breaks HMR.

## Evidence
* `backend/sandbox/executor.py`: `server_key = project_id` and `if server_key in _runtime_registry:` it kills the process tree.
* `frontend/src/panels/PreviewPanel.tsx`: `setIframeUrl(url + "?run_id=" + runId + "&t=" + Date.now())`.

## Risk Level
HIGH

## Recommended Stabilization
* Change `server_key` to `project_id_run_id` to allow multiple concurrent runs per project.
* Remove `Date.now()` from iframe url and rely on standard Vite/React HMR for updates.

## Constraints
* preserve current architecture
* no major refactor
* no subsystem rewrite

## Codex Repair Task
Change `server_key` in `executor.py` from `project_id` to `f"{project_id}_{run_id}"` and map port allocation per run.

---

# SYSTEM AUDIT

## Area
Orchestration Drift Risk

## Symptoms
* Mixed execution models: The planner generates a strictly sequenced `TaskGraph` (in shadow mode), but the actual file writing is driven by a single-shot `complete` call that generates raw files. 
* High risk of monolithic collapse. The scanner then attempts to validate the raw files against the `TaskGraph`, emitting warnings if the generator failed to separate concerns.
* Unstable execution chains: Shadow planning and patch simulation happen alongside monolithic full generation.

## Root Cause Hypothesis
* The system is migrating from a single-shot LLM generator to an agentic planner (`ProjectMapper` -> `TaskGraph` -> `PatchEngine`), but currently executes BOTH, discarding the structural safety of the patch engine for the actual file writes.
* The LLM prompt explicitly contains rules against monoliths but relies entirely on LLM compliance rather than forcing component-level generation via the task graph.

## Evidence
* `backend/orchestrator/project_orchestrator.py`: `TaskExecutor` executes `shadow_execution_callback` to build `PatchOperation`s and simulate them. But later, `raw = complete(system_prompt, user_prompt)` generates the entire project in one go using `===FILE===` delimiters, completely bypassing the patch simulator's safety boundaries.

## Risk Level
CRITICAL

## Recommended Stabilization
* Transition file generation exclusively to the `PatchEngine` using the generated `TaskGraph`. Stop executing the single-shot `complete()` fallback if the TaskGraph successfully generates patches.
* If shadow mode is kept, remove the duplication of LLM calls to reduce cost and drift.

## Constraints
* preserve current architecture
* no major refactor
* no subsystem rewrite

## Codex Repair Task
Disable the monolithic `complete` call in `project_orchestrator.py` and promote the `shadow_execution_callback`'s simulated patches to actual disk writes.

---

# SYSTEM AUDIT

## Area
Dependency Handling

## Symptoms
* Installation runs async via `run_in_executor` in `executor.py`, but execution readiness in `project_orchestrator.py` doesn't strictly block runtime launch until dependency installation is complete. 
* `_validate_react_vite_environment` happens before install/build, but there is no explicit barrier ensuring `npm install` finishes before `npm run dev` in the orchestrator pipeline.

## Root Cause Hypothesis
* The orchestrator assumes dependency installation is either instantaneous or handled externally. The `run_dev_server_array_async` monitors ports but will crash if `node_modules` is not fully hydrated.

## Evidence
* `backend/orchestrator/project_orchestrator.py`: Emits `environment_contract` but doesn't track install lockfiles explicitly in the orchestration flow.
* `backend/sandbox/executor.py`: `run_dev_server_async` starts subprocess directly.

## Risk Level
MEDIUM

## Recommended Stabilization
* Add explicit readiness barrier checking `node_modules` existence and `package.json` hash matching lockfile before starting dev server.

## Constraints
* preserve current architecture
* no major refactor
* no subsystem rewrite

## Codex Repair Task
Implement a dependency readiness barrier in `project_orchestrator.py` before invoking `run_dev_server_array_async`.
