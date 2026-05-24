# AI Agent Workspace — Implementation Plan

## Architecture Vision

```text
Prompt → Project Scan → Framework Detection → Skill Activation
  → Planning → File Modification → Runtime Validation
  → Error Detection → Repair Loop
```

## Phase Status

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ Done | Created missing `sandbox/executor.py` (actually exists) |
| 1 | ✅ Done | Skill Registry — `core/skills/` (interfaces, registry, built-in) |
| 2 | ✅ Done | Project Scanner — `core/scanner/` (detectors + engine) |
| 3 | ✅ Done | Framework Router — `core/router/` (capability-based routing) |
| 4 | ✅ Done | Project Patcher — `core/patcher/` (safe modification) |
| 5 | ✅ Done | Error Observer — `core/observer/` (error classification) |
| 6 | ✅ Done | AI Skill UI — frontend SkillsPanel + skills store |
| 7 | 🔲 Pending | Full orchestrator integration (uses skills by default) |
| 8 | 🔲 Pending | PHP/Laravel execution support |

## New Files Created

### Backend Core (`backend/core/`)

| File | Purpose |
|------|---------|
| `skills/__init__.py` | Package marker |
| `skills/interfaces.py` | `SkillMetadata` dataclass + `BaseSkill` ABC |
| `skills/registry.py` | Dynamic skill registry with capability/language/type lookup |
| `skills/builtin/__init__.py` | Package marker |
| `skills/builtin/react_vite.py` | React+Vite framework skill |
| `skills/builtin/node_backend.py` | Node.js backend skill |
| `skills/builtin/laravel.py` | Laravel skill (detection only — TODO execution) |
| `scanner/__init__.py` | Package marker |
| `scanner/detectors.py` | Filesystem detectors for 15+ frameworks/languages |
| `scanner/engine.py` | `scan_project()` → `ProjectScanResult` |
| `router/__init__.py` | Package marker |
| `router/routes.py` | `route_for_scan()`, `route_for_prompt()` |
| `patcher/__init__.py` | Package marker |
| `patcher/patch.py` | `PatchPlan`, `apply_patch_plan()`, target selection |
| `observer/__init__.py` | Package marker |
| `observer/errors.py` | `classify_error_line()`, `analyze_build_output()`, 11 error categories |
| `integration.py` | Facade linking all new systems |

### Backend Schema Updates (`backend/models/schemas.py`)

| Schema | Purpose |
|--------|---------|
| `SkillMetaSchema` | REST response for skill metadata |
| `ScanResultSchema` | REST response for project scan |
| `RouteResultSchema` | REST response for skill routing |
| `DiagnosticSchema` | REST response for error diagnostics |

### Backend Routes (added to `backend/main.py`)

| Route | Purpose |
|-------|---------|
| `GET /skills` | List all registered skills |
| `POST /scan` | Scan a project directory |
| `POST /route-from-scan` | Scan + route skills |

### Frontend (`frontend/src/`)

| File | Purpose |
|------|---------|
| `stores/skills.store.ts` | Zustand store for skill state |
| `panels/SkillsPanel.tsx` | UI panel to view/enable/disable skills |
| `services/api.ts` | Added `scan()`, `routeFromScan()`, `fetchSkills()` |

## Files Modified

| File | Change |
|------|--------|
| `backend/main.py` | Register built-in skills on startup; add `/skills`, `/scan`, `/route-from-scan` endpoints |
| `backend/models/schemas.py` | Added `SkillMetaSchema`, `ScanResultSchema`, `RouteResultSchema`, `DiagnosticSchema` |
| `frontend/src/layouts/WorkspaceLayout.tsx` | Added active view state; render SkillsPanel; fetch skills on mount |
| `frontend/src/panels/SidebarPanel.tsx` | Added skills nav icon; props for active view + navigation |
| `frontend/src/services/api.ts` | Added `scan()`, `routeFromScan()`, `fetchSkills()` methods |

## Extension Points

### Adding a new framework skill
1. Create `backend/core/skills/builtin/my_framework.py`
2. Implement `BaseSkill` with metadata (name, language, capabilities, tags)
3. Register in `backend/main.py` `_register_builtin_skills()`
4. Add detection rules in `backend/core/scanner/detectors.py`

### Adding a new scanner detector
1. Add function in `backend/core/scanner/detectors.py`
2. Call it in `scan_project()` in `engine.py`
3. Add field to `ProjectScanResult` if needed

### Adding a new error category
1. Add enum value to `ErrorCategory` in `observer/errors.py`
2. Add regex pattern + classify function
3. Add suggestion in `_suggest_fix()`
