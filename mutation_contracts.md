# Mutation Contracts

## 1. PatchOperation
**Required Fields:**
- \patch_type\ (string)
- \	arget_file\ (string)
- \	arget_region\ (object: start_line, end_line)
- \grounding_context\ (object: surrounding_lines, nearby_symbols)
- \confidence_score\ (number)

**Forbidden States:**
- Missing \	arget_region\ coordinates.
- \	arget_file\ path escaping the workspace boundaries.

## 2. ReplayReport
**Required Fields:**
- \patch_id\ (string)
- \eplay_safety\ (enum: 'safe', 'degraded', 'unsafe')
- \drift_state\ (string)
- \elocated_region\ (object)
- \stability_score\ (number)

**Invariants:**
- If \	arget_symbol\ is missing from the file, \eplay_safety\ MUST be 'unsafe'.

## 3. SimulationReport
**Required Fields:**
- \patch_id\ (string)
- \status\ (enum: 'applied', 'skipped')
- \syntax_sanity\ (object)
- \simulation_confidence_score\ (number)

**Forbidden States:**
- \status\ == 'applied' when \eplay_safety\ was 'unsafe'.
