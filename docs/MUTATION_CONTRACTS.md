# MUTATION CONTRACTS

These schemas represent the non-negotiable data boundaries of the execution pipeline.

## 1. PatchOperation
**Required Fields:**
- `patch_type` (string: append_import, inject_component, etc.)
- `target_file` (string: relative path)
- `target_region` (object: start_line, end_line)
- `grounding_context` (object: surrounding_lines, nearby_symbols)
- `confidence_score` (number: 0.0 - 1.0)

**Forbidden States:**
- Missing `target_region` coordinates.
- `target_file` path escaping the workspace boundaries (e.g., using `../` to break out).

## 2. ReplayReport
**Required Fields:**
- `patch_id` (string)
- `replay_safety` (enum: 'safe', 'degraded', 'unsafe')
- `drift_state` (string)
- `relocated_region` (object)
- `stability_score` (number: 0.0 - 1.0)
- `duplicate_injection_detected` (boolean)

**Invariants:**
- If `target_symbol` is missing from the file, `replay_safety` MUST be 'unsafe'.
- If `duplicate_injection_detected` is true, `replay_safety` MUST be 'unsafe'.

## 3. SimulationReport
**Required Fields:**
- `patch_id` (string)
- `status` (enum: 'applied', 'skipped')
- `skipped_reasons` (array of strings)
- `syntax_sanity` (object: passed, balance: {braces, brackets, parens})
- `simulation_confidence_score` (number: 0.0 - 1.0)

**Forbidden States:**
- `status` == 'applied' when `replay_safety` was 'unsafe'.
