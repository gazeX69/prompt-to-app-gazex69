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
    existing_artifact_context: Dict[str, str] = field(default_factory=dict)
    existing_file_summaries: Dict[str, List[str]] = field(default_factory=dict)
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
                            
        # 3. Read existing workspace files for allowed paths (only if not already modified in this session)
        for path in task.allowed_write_paths:
            if path in bundle.dependency_outputs or path in bundle.related_proposed_files:
                continue
            clean_path = path.lstrip("/\\")
            full_path = os.path.join(self.project_root, clean_path)
            if os.path.isfile(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        bundle.readable_files[path] = f.read()
                except Exception:
                    pass

        # 4. Existing artifact context for required semantic handoffs.
        self._hydrate_required_artifacts(task, bundle)
        self._hydrate_existing_file_summaries(task, bundle)
        
        return bundle

    def _hydrate_required_artifacts(self, task: ExecutionTask, bundle: TaskContextBundle) -> None:
        required_artifacts = list(getattr(task, "requires_artifacts", []) or [])
        if not required_artifacts:
            return

        for artifact in required_artifacts:
            for producer in self.task_graph.tasks.values():
                if producer.id == task.id:
                    continue
                if artifact not in (getattr(producer, "produces_artifacts", []) or []):
                    continue
                for file_path, phys_path in producer.proposed_artifacts.items():
                    try:
                        with open(phys_path, "r", encoding="utf-8") as f:
                            content = f.read()
                    except Exception as e:
                        bundle.warnings.append(f"Failed to read artifact source {artifact} from {file_path}: {e}")
                        continue
                    snippet = extract_symbol_definition(content, artifact) or content
                    bundle.existing_artifact_context[artifact] = f"Source file: {file_path}\n{snippet}"
                    if file_path not in bundle.dependency_outputs:
                        bundle.dependency_outputs[file_path] = content
                    break
                if artifact in bundle.existing_artifact_context:
                    break

    def _hydrate_existing_file_summaries(self, task: ExecutionTask, bundle: TaskContextBundle) -> None:
        candidate_files = {
            **bundle.readable_files,
            **bundle.dependency_outputs,
            **bundle.related_proposed_files,
        }

        common_paths = ["src/types.ts"]
        for common_path in common_paths:
            if common_path in candidate_files:
                continue
            full_path = os.path.join(self.project_root, common_path)
            if os.path.isfile(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        candidate_files[common_path] = f.read()
                except Exception:
                    pass

        for file_path, content in candidate_files.items():
            symbols = extract_exported_symbols(content)
            if symbols:
                bundle.existing_file_summaries[file_path] = symbols
                for symbol in symbols:
                    if symbol not in bundle.known_symbols:
                        bundle.known_symbols.append(symbol)
        
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


def extract_exported_symbols(content: str) -> List[str]:
    if not content:
        return []
    patterns = [
        r"\bexport\s+interface\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+type\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+enum\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+const\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+function\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\bexport\s+default\s+function\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    symbols: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            symbol = match.group(1)
            if symbol not in symbols:
                symbols.append(symbol)
    return symbols


def extract_symbol_definition(content: str, symbol: str) -> Optional[str]:
    if not content or not symbol:
        return None

    escaped = re.escape(symbol)
    block_patterns = [
        rf"\bexport\s+interface\s+{escaped}\s*\{{.*?\n\}}",
        rf"\bexport\s+type\s+{escaped}\s*=.*?(?=\n\n|\nexport\b|\Z)",
        rf"\bexport\s+enum\s+{escaped}\s*\{{.*?\n\}}",
        rf"\bexport\s+function\s+{escaped}\s*\([^)]*\)\s*\{{.*?(?=\nexport\b|\Z)",
        rf"\bexport\s+default\s+function\s+{escaped}\s*\([^)]*\)\s*\{{.*?(?=\nexport\b|\Z)",
        rf"\bexport\s+const\s+{escaped}\b.*?(?=\nexport\b|\Z)",
        rf"\bexport\s+class\s+{escaped}\b.*?(?=\nexport\b|\Z)",
    ]
    for pattern in block_patterns:
        match = re.search(pattern, content, flags=re.DOTALL)
        if match:
            return match.group(0).strip()
    return None


def format_existing_code_reuse_context(bundle: TaskContextBundle) -> str:
    if not bundle.existing_artifact_context and not bundle.existing_file_summaries:
        return ""

    parts = ["\n\n=== EXISTING CODE REUSE CONTEXT ==="]
    for artifact, definition in bundle.existing_artifact_context.items():
        parts.append(f"\nCurrent {artifact} definition:\n{definition}")

    if bundle.existing_file_summaries:
        parts.append("\nExisting exported symbols:")
        for file_path, symbols in bundle.existing_file_summaries.items():
            parts.append(f"- {file_path}: {', '.join(symbols)}")

    parts.append(
        "\nReuse rules:\n"
        "- USE EXISTING TYPES.\n"
        "- Do not redefine existing interfaces, hooks, stores, or components.\n"
        "- Do not create a second schema for an existing type.\n"
        "- If a type already exists, all object literals for that type must satisfy the existing interface.\n"
        "- Import and reuse existing exports instead of recreating them.\n"
        "=== END EXISTING CODE REUSE CONTEXT ===\n"
    )
    return "\n".join(parts)


def _parse_interface_fields(content: str) -> Dict[str, Set[str]]:
    interfaces: Dict[str, Set[str]] = {}
    for match in re.finditer(r"\bexport\s+interface\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(?P<body>.*?)\n\}", content, flags=re.DOTALL):
        name = match.group(1)
        body = match.group("body")
        fields = set()
        for field_match in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\??\s*:", body, flags=re.MULTILINE):
            fields.add(field_match.group(1))
        if fields:
            interfaces[name] = fields
    return interfaces


def _object_keys(object_body: str) -> Set[str]:
    keys: Set[str] = set()
    for match in re.finditer(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", object_body, flags=re.MULTILINE):
        keys.add(match.group(1))
    return keys


def detect_schema_drift(files: Dict[str, str]) -> List[str]:
    interfaces: Dict[str, Set[str]] = {}
    for content in files.values():
        interfaces.update(_parse_interface_fields(content))

    findings: List[str] = []
    if not interfaces:
        return findings

    for file_path, content in files.items():
        for type_name, required_fields in interfaces.items():
            array_pattern = rf":\s*{re.escape(type_name)}\[\]\s*=\s*\[(?P<body>.*?)\]"
            for array_match in re.finditer(array_pattern, content, flags=re.DOTALL):
                for object_match in re.finditer(r"\{(?P<object>.*?)\}", array_match.group("body"), flags=re.DOTALL):
                    keys = _object_keys(object_match.group("object"))
                    if not keys:
                        continue
                    missing = sorted(required_fields - keys)
                    if missing:
                        findings.append(
                            f"Schema Drift Detected: {file_path} has {type_name} object missing fields: {', '.join(missing)}"
                        )

            object_pattern = rf":\s*{re.escape(type_name)}\s*=\s*\{{(?P<object>.*?)\}}"
            for object_match in re.finditer(object_pattern, content, flags=re.DOTALL):
                keys = _object_keys(object_match.group("object"))
                if not keys:
                    continue
                missing = sorted(required_fields - keys)
                if missing:
                    findings.append(
                        f"Schema Drift Detected: {file_path} has {type_name} object missing fields: {', '.join(missing)}"
                    )

    return findings
