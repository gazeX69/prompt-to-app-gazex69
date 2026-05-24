# VERIFICATION RULES

Future agents MUST verify their work against these exact conditions before claiming a task is successful.

## 1. Type Safety
- **Rule:** The frontend application must compile without TypeScript errors.
- **Verification:** Run `npm run build` in `frontend/`. It must return exit code 0.

## 2. API Stability
- **Rule:** The FastAPI backend must start without schema conflicts.
- **Verification:** The Python server must boot, and `GET /workspaces/{id}/readiness` must return a valid JSON payload without throwing a 500.

## 3. Execution Readiness Matrix
- **Rule:** If you are testing a patch pipeline feature, you must ensure the patch flows entirely through to the Simulation output.
- **Verification:** Check `GET /workspaces/{id}/readiness`. The `system_simulation_confidence` must not crash to 0 unless you are explicitly testing an unsafe input.

## 4. UI Rendering Safety
- **Rule:** New overlays in `FileInspector.tsx` must not break the component tree if data is missing.
- **Verification:** Ensure `?` optional chaining is used extensively when accessing `.orchestration` merged payload arrays (e.g., `p.replay?.replay_safety`).
