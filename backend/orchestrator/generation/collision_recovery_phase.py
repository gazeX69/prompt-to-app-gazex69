import re
from typing import Any

from backend.orchestrator.patch_engine import PatchOperation, apply_patch

def extract_app_tsx_metadata(patch) -> dict:
    import re
    metadata = {
        "imports": [],
        "routes": [],
        "states_or_props": []
    }
    content = getattr(patch, "content", "")
    if not content:
        return metadata
        
    # 1. Extract imports
    import_matches = re.findall(r"import\s+.*?\s+from\s+['\"].*?['\'];?", content)
    for imp in import_matches:
        metadata["imports"].append(imp.strip())
        
    # 2. Extract routes (Route declarations)
    route_matches = re.findall(r"^\s*(?:<Route|</Route>)\s*.*", content, flags=re.MULTILINE)
    for route in route_matches:
        metadata["routes"].append(route.strip())
        
    # 3. Extract states/hooks inside function App
    state_matches = re.findall(r"(?:const|let)\s+(?:\[.*?\]|\{.*?\}|\w+)\s*=\s*useState\(.*?\)", content, flags=re.DOTALL)
    for state in state_matches:
        metadata["states_or_props"].append(state.strip())
        
    hook_matches = re.findall(r"(?:const|let)\s+(?:\[.*?\]|\{.*?\}|\w+)\s*=\s*use[A-Za-z0-9_]+\(.*?\)", content, flags=re.DOTALL)
    for hook in hook_matches:
        h_strip = hook.strip()
        if "useState(" not in h_strip and h_strip not in metadata["states_or_props"]:
            metadata["states_or_props"].append(h_strip)
        
    return metadata


def consolidate_app_tsx(base_content: str, imports: list, routes: list, states: list) -> str:
    import re
    content = base_content.replace("\r\n", "\n")
    
    # Add Imports
    import_lines = re.findall(r"^(?:import|from)\s+.*", content, flags=re.MULTILINE)
    unique_imports = []
    for imp in imports:
        if imp not in content and imp not in unique_imports:
            unique_imports.append(imp)
            
    if unique_imports:
        import_block = "\n".join(unique_imports)
        if import_lines:
            last_import = import_lines[-1]
            content = content.replace(last_import, last_import + "\n" + import_block, 1)
        else:
            content = import_block + "\n\n" + content
            
    # Add States/Hooks
    unique_states = []
    for st in states:
        if st not in content and st not in unique_states:
            unique_states.append(st)
            
    if unique_states:
        state_block = "\n  " + "\n  ".join(unique_states) + "\n"
        match = re.search(r"(?:export\s+default\s+)?function\s+App\s*\([^\)]*\)\s*\{", content)
        if match:
            idx = match.end()
            content = content[:idx] + state_block + content[idx:]
            
    # Add Routes
    unique_routes = []
    for r in routes:
        if r not in content and r not in unique_routes:
            unique_routes.append(r)
            
    if unique_routes:
        formatted_routes = "\n      " + "\n      ".join(unique_routes)
        routes_match = re.search(r"<Routes[^>]*>", content)
        if routes_match:
            idx = routes_match.end()
            content = content[:idx] + formatted_routes + content[idx:]
            
    return content


def _background_values(content: str) -> list[str]:
    return [
        match.group(1).strip().lower()
        for match in re.finditer(r"(?i)\bbackground(?:-color)?\s*:\s*([^;}{]+)", content or "")
    ]


def _preservation_violations(target: str, old_content: str, new_content: str, change_scope: dict | None) -> list[str]:
    if not change_scope or change_scope.get("scope_size") != "small":
        return []
    facts = (change_scope.get("preserved_source_facts") or {}).get("relevant_preservation_facts") or []
    violations: list[str] = []
    for fact in facts:
        if not str(fact).startswith(f"{target}:"):
            continue
        if " = " in str(fact):
            expected = str(fact).split(" = ", 1)[1].strip()
            if expected and expected.lower() in (old_content or "").lower() and expected.lower() not in (new_content or "").lower():
                violations.append(f"Removed preserved source fact from {target}: {fact}")
        elif "visible text '" in str(fact):
            expected = str(fact).split("visible text '", 1)[1].split("'", 1)[0]
            if expected and expected in (old_content or "") and expected not in (new_content or ""):
                violations.append(f"Removed preserved visible text from {target}: {expected}")

    if change_scope.get("change_type") == "content_addition":
        old_backgrounds = set(_background_values(old_content))
        new_backgrounds = set(_background_values(new_content))
        introduced_backgrounds = new_backgrounds - old_backgrounds
        if introduced_backgrounds:
            violations.append(
                "Content addition introduced background styling that was not requested: "
                + ", ".join(sorted(introduced_backgrounds))
            )
    return violations


def compose_conflicting_file_patches(
    target_file: str,
    p_list: list[tuple[str, PatchOperation]],
    sorted_task_ids: list[str],
) -> tuple[list[PatchOperation] | None, dict[str, Any]]:
    """Fold same-file collision patches into one final create_file patch.

    This is intentionally narrow: it only handles collisions that already have a
    create_file base. That prevents stale replace_block anchors from being
    replayed as a raw chain during the second dry-run.
    """
    ordered_patches: list[tuple[str, PatchOperation]] = []
    for task_id in sorted_task_ids:
        ordered_patches.extend((tid, patch) for tid, patch in p_list if tid == task_id)

    first_create_index = next(
        (index for index, (_task_id, patch) in enumerate(ordered_patches) if patch.operation == "create_file"),
        None,
    )
    if first_create_index is None:
        return None, {"stale_anchor": False, "folded": False, "notes": []}

    notes: list[str] = []
    stale_anchor = False
    base_task_id, base_patch = ordered_patches[first_create_index]
    composed_content = base_patch.content
    notes.append(f"base create_file from {base_task_id}")

    for task_id, patch in ordered_patches[first_create_index + 1:]:
        if patch.operation == "create_file":
            if patch.content.strip() == composed_content.strip():
                notes.append(f"duplicate create_file from {task_id} merged")
            else:
                notes.append(f"different create_file from {task_id} skipped; preserving first base")
            continue

        try:
            composed_content = apply_patch(patch, composed_content)
            notes.append(f"applied {patch.operation} from {task_id}")
        except Exception as exc:
            if patch.operation == "replace_block":
                stale_anchor = True
                if _looks_like_full_file_replacement(target_file, patch.content):
                    composed_content = patch.content
                    notes.append(f"stale replace_block from {task_id} recovered as full-file replacement")
                else:
                    notes.append(f"stale replace_block from {task_id} skipped: {exc}")
                continue
            notes.append(f"{patch.operation} from {task_id} failed and was kept out of folded patch: {exc}")

    folded_patch = PatchOperation(
        operation="create_file",
        target=target_file,
        content=composed_content,
    )
    return [folded_patch], {
        "stale_anchor": stale_anchor,
        "folded": True,
        "notes": notes,
    }


def _looks_like_full_file_replacement(target_file: str, content: str | None) -> bool:
    if not content or not target_file.endswith((".ts", ".tsx", ".js", ".jsx")):
        return False
    stripped = content.strip()
    if len(stripped.splitlines()) < 5:
        return False
    return (
        "export default" in stripped
        or "function " in stripped and "return (" in stripped
        or stripped.startswith("import ") and ("export " in stripped or "const " in stripped)
    )

