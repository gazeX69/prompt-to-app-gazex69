import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class PatchOperation:
    operation: str  # create_file, append_to_file, insert_import, replace_block, modify_json_key, inject_component, append_php_include
    target: str
    content: str
    find: Optional[str] = None
    after: Optional[str] = None
    before: Optional[str] = None
    key_path: Optional[str] = None  # For modify_json_key
    
    @classmethod
    def from_dict(cls, data: dict):
        operation = data.get("operation") or data.get("operation_type") or data.get("type") or data.get("op") or data.get("action")
        
        # Resilient fallback: if the LLM nested the fields inside the operation name as a key
        # e.g., {"create_file": {"target": "...", "content": "..."}}
        if not operation and len(data) == 1:
            k = list(data.keys())[0]
            if isinstance(data[k], dict):
                operation = k
                data = data[k]
        elif not operation:
            known_ops = {"create_file", "append_to_file", "insert_import", "replace_block", "modify_json_key", "inject_component", "append_php_include"}
            for op in known_ops:
                if op in data:
                    if isinstance(data[op], dict):
                        operation = op
                        data = data[op]
                        break
                    elif isinstance(data[op], str):
                        operation = op
                        data = data.copy()
                        data["target"] = data[op]
                        break
                    
        raw_target = data.get("target") or data.get("target_file") or data.get("file") or data.get("path") or ""
        cleaned_target = raw_target.lstrip("/\\") if isinstance(raw_target, str) else ""
        
        def clean_escaped_newlines(s):
            if not isinstance(s, str):
                return s
            return s.replace("\\n", "\n").replace("\\r", "\r")
            
        content = clean_escaped_newlines(data.get("content") or data.get("code") or data.get("text") or "")
        find = clean_escaped_newlines(data.get("find") or data.get("find_block") or data.get("find_string"))
        after = clean_escaped_newlines(data.get("after"))
        before = clean_escaped_newlines(data.get("before"))
        
        return cls(
            operation=operation,
            target=cleaned_target,
            content=content,
            find=find,
            after=after,
            before=before,
            key_path=data.get("key_path")
        )

@dataclass
class PatchReport:
    operation: PatchOperation
    classification: str  # safe_append, safe_insert, risky_replace, full_overwrite, ambiguous, forbidden
    success: bool
    error: Optional[str] = None

class PatchSafetyEngine:
    def __init__(self, allowed_paths: List[str], forbidden_paths: List[str]):
        self.allowed_paths = allowed_paths
        self.forbidden_paths = forbidden_paths
        
    def classify(self, patch: PatchOperation) -> str:
        # Check forbidden
        if any(patch.target.startswith(fp) or patch.target == fp for fp in self.forbidden_paths):
            return "forbidden"
        if self.allowed_paths:
            if any(patch.target.startswith(ap) or patch.target == ap for ap in self.allowed_paths):
                pass
            else:
                # Resilient fallback: if allowed_paths contains a src/ file, also allow src/ directory writes
                has_src_access = any(ap.startswith("src/") for ap in self.allowed_paths)
                if has_src_access and patch.target.startswith("src/"):
                    pass
                elif any(ap == "tsconfig.json" for ap in self.allowed_paths) and patch.target in ["tsconfig.app.json", "tsconfig.node.json"]:
                    pass
                elif any(ap in ["tsconfig.json", "vite.config.ts", "package.json"] for ap in self.allowed_paths) and patch.target in [
                    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs",
                    "postcss.config.js", "postcss.config.ts", "postcss.config.cjs",
                    "eslint.config.js", ".gitignore"
                ]:
                    pass
                else:
                    return "forbidden"
            
        if patch.operation == "create_file":
            # If file already exists, it would be full_overwrite, but this depends on context
            return "full_overwrite"
        elif patch.operation in ["append_to_file", "append_php_include"]:
            return "safe_append"
        elif patch.operation == "insert_import":
            return "safe_insert"
        elif patch.operation == "modify_json_key":
            return "safe_insert"
        elif patch.operation == "inject_component":
            return "safe_insert"
        elif patch.operation == "replace_block":
            if not patch.find:
                return "ambiguous"
            return "risky_replace"
        return "ambiguous"

class PatchSimulator:
    def __init__(self, workspace_root: str, session_id: str, task_id: str):
        self.workspace_root = workspace_root
        self.session_id = session_id
        self.task_id = task_id
        self.sim_dir = os.path.join(workspace_root, ".orchestration", "patch_simulations", session_id, task_id)
        
    def simulate(self, patches: List[PatchOperation], current_files: Dict[str, str], engine: PatchSafetyEngine) -> List[PatchReport]:
        reports = []
        os.makedirs(self.sim_dir, exist_ok=True)
        
        simulated_files = current_files.copy()
        
        for idx, patch in enumerate(patches):
            report = PatchReport(operation=patch, classification=engine.classify(patch), success=False)
            if report.classification == "forbidden":
                report.error = "Target is forbidden"
                reports.append(report)
                continue
                
            file_content = simulated_files.get(patch.target, "")
            
            try:
                simulated_files[patch.target] = apply_patch(patch, file_content)
                report.success = True
            except Exception as e:
                report.error = str(e)
                
            reports.append(report)
            
        # Write simulated files
        for fpath, fcontent in simulated_files.items():
            clean_fpath = fpath.lstrip("/\\")
            dest = os.path.join(self.sim_dir, clean_fpath.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(fcontent)
                
        # Write report
        report_path = os.path.join(self.sim_dir, "patch_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump([{
                "operation": r.operation.operation,
                "target": r.operation.target,
                "classification": r.classification,
                "success": r.success,
                "error": r.error
            } for r in reports], f, indent=2)
            
        return reports


def apply_patch(patch: PatchOperation, file_content: str) -> str:
    # Universal newline normalization to \n for consistent internal string operations
    normalized_content = file_content.replace("\r\n", "\n")
    
    if patch.operation == "create_file":
        return patch.content
        
    elif patch.operation == "append_to_file":
        if normalized_content and not normalized_content.endswith("\n"):
            normalized_content += "\n"
        return normalized_content + patch.content
        
    elif patch.operation == "insert_import":
        imports = re.findall(r"^(?:import|from)\s+.*", normalized_content, flags=re.MULTILINE)
        if imports:
            last_import = imports[-1]
            return normalized_content.replace(last_import, last_import + "\n" + patch.content, 1)
        else:
            if normalized_content.strip():
                return patch.content + "\n\n" + normalized_content
            else:
                return patch.content
                
    elif patch.operation == "append_php_include":
        if "<?php" in normalized_content:
            return normalized_content.replace("<?php", "<?php\n" + patch.content, 1)
        else:
            return "<?php\n" + patch.content + "\n?>\n" + normalized_content
            
    elif patch.operation == "modify_json_key":
        try:
            data = json.loads(normalized_content) if normalized_content.strip() else {}
        except Exception as e:
            raise ValueError(f"Failed to parse JSON: {e}")
            
        if patch.key_path:
            val = patch.content
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            data[patch.key_path] = val
        return json.dumps(data, indent=2)
        
def compile_resilient_regex(find_str: str) -> str:
    # Normalize newlines
    find_str = find_str.replace("\r\n", "\n")
    
    # Tokenize the find string to build a regex that allows optional symbols and flexible spaces
    token_re = re.compile(
        r"(?P<string>['\"\x60](?:\\.|[^'\"\x60])*['\"\x60])|"
        r"(?P<word>[a-zA-Z0-9_]+)|"
        r"(?P<space>\s+)|"
        r"(?P<semicolon>;)|"
        r"(?P<comma>,)|"
        r"(?P<char>.)",
        re.DOTALL
    )
    
    pattern_parts = []
    
    for match in token_re.finditer(find_str):
        if match.group("string"):
            val = match.group("string")
            content = val[1:-1]
            escaped_content = re.escape(content)
            # If no extension exists, allow optional .js, .jsx, .ts, .tsx
            if not re.search(r"\.[a-zA-Z0-9]+$", content):
                escaped_content += r"(?:\.[jt]sx?)?"
            else:
                # If there is an extension, make it optional as well, just in case
                ext_match = re.search(r"(\.[jt]sx?)$", content)
                if ext_match:
                    ext = ext_match.group(1)
                    escaped_content = escaped_content[:-len(re.escape(ext))] + r"(?:\.[jt]sx?)?"
            
            pattern_parts.append(rf"['\"\x60]{escaped_content}['\"\x60]")
        elif match.group("word"):
            pattern_parts.append(re.escape(match.group("word")))
        elif match.group("space"):
            pattern_parts.append(r"\s+")
        elif match.group("semicolon"):
            pattern_parts.append(r"\s*;?")
        elif match.group("comma"):
            pattern_parts.append(r"\s*,?")
        elif match.group("char"):
            char = match.group("char")
            if char in "()[]{}<>.+-*/=!&|":
                pattern_parts.append(rf"\s*{re.escape(char)}\s*")
            else:
                pattern_parts.append(re.escape(char))
                
    pattern = "".join(pattern_parts)
    
    # Merge redundant spaces
    pattern = re.sub(r"(\\s\*)+", r"\\s*", pattern)
    pattern = re.sub(r"\\s\+\\s\*", r"\\s+", pattern)
    pattern = re.sub(r"\\s\*\\s\+", r"\\s+", pattern)
    pattern = re.sub(r"(\\s\+)+", r"\\s+", pattern)
    
    return pattern


def apply_patch(patch: PatchOperation, file_content: str) -> str:
    # Universal newline normalization to \n for consistent internal string operations
    normalized_content = file_content.replace("\r\n", "\n")
    
    if patch.operation == "create_file":
        return patch.content
        
    elif patch.operation == "append_to_file":
        if normalized_content and not normalized_content.endswith("\n"):
            normalized_content += "\n"
        return normalized_content + patch.content
        
    elif patch.operation == "insert_import":
        imports = re.findall(r"^(?:import|from)\s+.*", normalized_content, flags=re.MULTILINE)
        if imports:
            last_import = imports[-1]
            return normalized_content.replace(last_import, last_import + "\n" + patch.content, 1)
        else:
            if normalized_content.strip():
                return patch.content + "\n\n" + normalized_content
            else:
                return patch.content
                
    elif patch.operation == "append_php_include":
        if "<?php" in normalized_content:
            return normalized_content.replace("<?php", "<?php\n" + patch.content, 1)
        else:
            return "<?php\n" + patch.content + "\n?>\n" + normalized_content
            
    elif patch.operation == "modify_json_key":
        try:
            data = json.loads(normalized_content) if normalized_content.strip() else {}
        except Exception as e:
            raise ValueError(f"Failed to parse JSON: {e}")
            
        if patch.key_path:
            val = patch.content
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            data[patch.key_path] = val
        return json.dumps(data, indent=2)
        
    elif patch.operation == "replace_block":
        # Fallback for empty or whitespace-only target file:
        if not normalized_content.strip():
            return patch.content
            
        find_str = patch.find or ""
        normalized_find = find_str.replace("\r\n", "\n")
        
        # 1. Try exact match first
        if normalized_find and normalized_find in normalized_content:
            return normalized_content.replace(normalized_find, patch.content.replace("\r\n", "\n"), 1)
            
        # 2. Try advanced resilient regex matching
        if normalized_find:
            try:
                resilient_pattern = compile_resilient_regex(normalized_find)
                match = re.search(resilient_pattern, normalized_content)
                if match:
                    start, end = match.span()
                    return normalized_content[:start] + patch.content.replace("\r\n", "\n") + normalized_content[end:]
            except Exception:
                pass

        # 3. Try token-based resilient matching (legacy fallback)
        tokens = normalized_find.split()
        if tokens:
            escaped_tokens = [re.escape(t) for t in tokens]
            pattern_str = r"\s+".join(escaped_tokens)
            try:
                match = re.search(pattern_str, normalized_content)
                if match:
                    start, end = match.span()
                    return normalized_content[:start] + patch.content.replace("\r\n", "\n") + normalized_content[end:]
            except Exception:
                pass
                
        raise ValueError(f"Replace target block not found: {patch.find}")
        
    elif patch.operation == "inject_component":
        # Try after anchor first
        if patch.after:
            normalized_after = patch.after.replace("\r\n", "\n")
            if normalized_after in normalized_content:
                return normalized_content.replace(normalized_after, normalized_after + "\n" + patch.content.replace("\r\n", "\n"), 1)
                
            # Try advanced resilient regex matching for after
            try:
                resilient_pattern = compile_resilient_regex(normalized_after)
                match = re.search(resilient_pattern, normalized_content)
                if match:
                    start, end = match.span()
                    return normalized_content[:end] + "\n" + patch.content.replace("\r\n", "\n") + normalized_content[end:]
            except Exception:
                pass

            # Token search for after anchor (legacy fallback)
            tokens = normalized_after.split()
            if tokens:
                escaped_tokens = [re.escape(t) for t in tokens]
                pattern_str = r"\s+".join(escaped_tokens)
                try:
                    match = re.search(pattern_str, normalized_content)
                    if match:
                        start, end = match.span()
                        return normalized_content[:end] + "\n" + patch.content.replace("\r\n", "\n") + normalized_content[end:]
                except Exception:
                    pass
                    
        # Try before anchor next
        if patch.before:
            normalized_before = patch.before.replace("\r\n", "\n")
            if normalized_before in normalized_content:
                return normalized_content.replace(normalized_before, patch.content.replace("\r\n", "\n") + "\n" + normalized_before, 1)
                
            # Try advanced resilient regex matching for before
            try:
                resilient_pattern = compile_resilient_regex(normalized_before)
                match = re.search(resilient_pattern, normalized_content)
                if match:
                    start, end = match.span()
                    return normalized_content[:start] + patch.content.replace("\r\n", "\n") + "\n" + normalized_content[start:]
            except Exception:
                pass

            # Token search for before anchor (legacy fallback)
            tokens = normalized_before.split()
            if tokens:
                escaped_tokens = [re.escape(t) for t in tokens]
                pattern_str = r"\s+".join(escaped_tokens)
                try:
                    match = re.search(pattern_str, normalized_content)
                    if match:
                        start, end = match.span()
                        return normalized_content[:start] + patch.content.replace("\r\n", "\n") + "\n" + normalized_content[start:]
                except Exception:
                    pass
                    
        raise ValueError(f"Injection anchor block not found: after={patch.after}, before={patch.before}")
        
    else:
        raise ValueError(f"Unknown operation: {patch.operation}")
