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
        return cls(
            operation=data.get("operation"),
            target=data.get("target"),
            content=data.get("content", ""),
            find=data.get("find"),
            after=data.get("after"),
            before=data.get("before"),
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
        if self.allowed_paths and not any(patch.target.startswith(ap) or patch.target == ap for ap in self.allowed_paths):
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
                if patch.operation == "create_file":
                    simulated_files[patch.target] = patch.content
                elif patch.operation == "append_to_file":
                    simulated_files[patch.target] = file_content + "\n" + patch.content
                elif patch.operation == "insert_import":
                    # Lightweight parser: insert after last import or at top
                    imports = re.findall(r"^(?:import|from)\s+.*", file_content, flags=re.MULTILINE)
                    if imports:
                        last_import = imports[-1]
                        simulated_files[patch.target] = file_content.replace(last_import, last_import + "\n" + patch.content, 1)
                    else:
                        simulated_files[patch.target] = patch.content + "\n\n" + file_content
                elif patch.operation == "append_php_include":
                    if "<?php" in file_content:
                        simulated_files[patch.target] = file_content.replace("<?php", "<?php\n" + patch.content, 1)
                    else:
                        simulated_files[patch.target] = "<?php\n" + patch.content + "\n?>\n" + file_content
                elif patch.operation == "modify_json_key":
                    try:
                        data = json.loads(file_content) if file_content.strip() else {}
                        # Very simple key path logic (top-level only for now)
                        if patch.key_path:
                            data[patch.key_path] = json.loads(patch.content)
                        simulated_files[patch.target] = json.dumps(data, indent=2)
                    except json.JSONDecodeError as e:
                        report.error = f"Invalid JSON base: {e}"
                elif patch.operation == "replace_block":
                    if patch.find and patch.find in file_content:
                        simulated_files[patch.target] = file_content.replace(patch.find, patch.content, 1)
                    else:
                        report.error = "Find block not found in file"
                elif patch.operation == "inject_component":
                    if patch.after and patch.after in file_content:
                        simulated_files[patch.target] = file_content.replace(patch.after, patch.after + "\n" + patch.content, 1)
                    elif patch.before and patch.before in file_content:
                        simulated_files[patch.target] = file_content.replace(patch.before, patch.content + "\n" + patch.before, 1)
                    else:
                        report.error = "Injection target block not found"
                else:
                    report.error = "Unknown operation"
                    
                if not report.error:
                    report.success = True
            except Exception as e:
                report.error = str(e)
                
            reports.append(report)
            
        # Write simulated files
        for fpath, fcontent in simulated_files.items():
            dest = os.path.join(self.sim_dir, fpath.replace("/", os.sep))
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
