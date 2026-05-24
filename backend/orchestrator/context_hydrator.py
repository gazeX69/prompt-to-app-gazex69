import os
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional

from backend.orchestrator.task_graph import TaskGraph, ExecutionTask

@dataclass
class TaskContextBundle:
    readable_files: Dict[str, str] = field(default_factory=dict)
    dependency_outputs: Dict[str, str] = field(default_factory=dict)
    related_proposed_files: Dict[str, str] = field(default_factory=dict)
    known_symbols: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

@dataclass
class MergeSafetyReport:
    task_id: str
    collisions: List[str] = field(default_factory=list)
    missing_dependencies: List[str] = field(default_factory=list)
    stale_base_risks: List[str] = field(default_factory=list)
    safe_to_write: bool = True
    reason: str = "Safe"
    
    def to_dict(self):
        return {
            "task_id": self.task_id,
            "collisions": self.collisions,
            "missing_dependencies": self.missing_dependencies,
            "stale_base_risks": self.stale_base_risks,
            "safe_to_write": self.safe_to_write,
            "reason": self.reason
        }

class ContextHydrator:
    def __init__(self, project_root: str, session_id: str, task_graph: TaskGraph):
        self.project_root = project_root
        self.session_id = session_id
        self.task_graph = task_graph
        self.merge_reports: Dict[str, MergeSafetyReport] = {}
        
    def hydrate_context(self, task: ExecutionTask) -> TaskContextBundle:
        bundle = TaskContextBundle()
        
        # 1. Gather dependency outputs
        for dep_id in task.dependencies:
            dep_task = self.task_graph.get_task(dep_id)
            if dep_task:
                for file_path, phys_path in dep_task.proposed_artifacts.items():
                    try:
                        with open(phys_path, 'r', encoding='utf-8') as f:
                            bundle.dependency_outputs[file_path] = f.read()
                    except Exception as e:
                        bundle.warnings.append(f"Failed to read dependency output {file_path}: {e}")
                        
        # 2. Related proposed files from earlier non-dependency tasks (collision context)
        # We look at all COMPLETED tasks
        for prev_task in self.task_graph.tasks.values():
            if prev_task.id == task.id or prev_task.id in task.dependencies:
                continue
            if prev_task.status.value == "completed":
                # Find overlaps
                for p_file, phys_path in prev_task.proposed_artifacts.items():
                    if p_file in task.affected_files or any(p_file.startswith(ap) for ap in task.allowed_write_paths):
                        try:
                            with open(phys_path, 'r', encoding='utf-8') as f:
                                bundle.related_proposed_files[p_file] = f.read()
                        except:
                            pass
                            
        # 3. Read existing workspace files for allowed paths
        for path in task.allowed_write_paths:
            full_path = os.path.join(self.project_root, path)
            if os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        bundle.readable_files[path] = f.read()
                except Exception:
                    pass
        
        return bundle
        
    def check_merge_safety(self, task: ExecutionTask, proposed_files: List['GeneratedFile'], bundle: TaskContextBundle) -> MergeSafetyReport:
        report = MergeSafetyReport(task_id=task.id)
        
        # 1. Same-file collisions
        for pf in proposed_files:
            # Check if another task already touched this file
            touched_by_others = False
            for prev_task in self.task_graph.tasks.values():
                if prev_task.id != task.id and prev_task.status.value == "completed":
                    if pf.path in prev_task.proposed_artifacts:
                        touched_by_others = True
                        break
                        
            if touched_by_others:
                report.collisions.append(pf.path)
                report.safe_to_write = False
                report.reason = f"Unsafe collision: {pf.path} was proposed by a previous task. Full overwrite is unsafe."
                report.stale_base_risks.append(pf.path)

        # 2. Missing imports / includes detection (lightweight regex scan)
        for pf in proposed_files:
            content = pf.content
            # Basic React/TS import check
            # e.g., import { TodoList } from './components/TodoList'
            imports = re.findall(r"import\s+.*?\s+from\s+['\"](.*?)['\"]", content)
            for imp in imports:
                if imp.startswith('.'):
                    # Local import. We should check if it exists in bundle.dependency_outputs or related
                    # Note: this is a very basic path heuristic for validation purposes
                    base_name = os.path.basename(imp)
                    found = False
                    for bfile in list(bundle.dependency_outputs.keys()) + list(bundle.related_proposed_files.keys()):
                        if base_name in bfile:
                            found = True
                            break
                    if not found:
                        report.missing_dependencies.append(imp)
                        
        self.merge_reports[task.id] = report
        return report
        
    def save_reports(self, session_dir: str):
        report_path = os.path.join(session_dir, f"{self.session_id}.merge_safety.json")
        data = {tid: r.to_dict() for tid, r in self.merge_reports.items()}
        temp_path = report_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, report_path)
