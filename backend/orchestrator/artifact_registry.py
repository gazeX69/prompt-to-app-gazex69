import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class GeneratedArtifact:
    file_path: str
    artifact_type: str = "file"
    status: str = "unexpected" # 'matched', 'missing', 'unexpected', 'modified', 'orphan', 'ambiguous'
    producing_task_id: Optional[str] = None
    checksum: Optional[str] = None
    size_bytes: int = 0
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self):
        return {
            "file_path": self.file_path,
            "artifact_type": self.artifact_type,
            "status": self.status,
            "producing_task_id": self.producing_task_id,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            file_path=data.get("file_path"),
            artifact_type=data.get("artifact_type", "file"),
            status=data.get("status", "unexpected"),
            producing_task_id=data.get("producing_task_id"),
            checksum=data.get("checksum"),
            size_bytes=data.get("size_bytes", 0),
            created_at=data.get("created_at")
        )

@dataclass
class ArtifactRegistry:
    session_id: str
    artifacts: dict[str, GeneratedArtifact] = field(default_factory=dict)
    
    def add_actual_file(self, file_path: str, content: str):
        content_bytes = content.encode('utf-8') if isinstance(content, str) else content
        checksum = hashlib.sha256(content_bytes).hexdigest()
        self.artifacts[file_path] = GeneratedArtifact(
            file_path=file_path,
            artifact_type='file',
            status='unexpected',
            checksum=checksum,
            size_bytes=len(content_bytes)
        )
        
    def compare_with_plan(self, task_graph):
        """
        Compare actual generated files against expected_files/affected_files from TaskGraph.
        Assign status and task IDs.
        """
        planned_files = {} # path -> list of task_ids
        for task in task_graph.tasks.values():
            for f in task.affected_files:
                planned_files.setdefault(f, []).append(task.id)
                
        # Match actuals (Pass 1: Literal)
        for file_path, artifact in self.artifacts.items():
            if file_path in planned_files:
                tasks = planned_files[file_path]
                if len(tasks) == 1:
                    artifact.producing_task_id = tasks[0]
                    artifact.status = 'matched'
                else:
                    artifact.producing_task_id = tasks[-1] # Assign to last modifying task
                    artifact.status = 'ambiguous'
            else:
                artifact.status = 'orphan'
                
        # Find missing
        missing_planned = []
        for planned_file, tasks in planned_files.items():
            if planned_file not in self.artifacts:
                missing_planned.append((planned_file, tasks))

        # Pass 2: Semantic Matching for orphans
        orphans = [a for a in self.artifacts.values() if a.status == 'orphan']
        import os
        import re
        
        def _compute_semantic_similarity(actual_path: str, planned_path: str):
            actual_dir, actual_name = os.path.split(actual_path)
            planned_dir, planned_name = os.path.split(planned_path)
            actual_base, actual_ext = os.path.splitext(actual_name)
            planned_base, planned_ext = os.path.splitext(planned_name)
            
            def tokenize(s):
                tokens = re.split(r'([A-Z][a-z]+)|_|-|\.', s)
                return set(t.lower() for t in tokens if t and t.strip())
                
            actual_tokens = tokenize(actual_base)
            planned_tokens = tokenize(planned_base)
            
            intersection = actual_tokens.intersection(planned_tokens)
            union = actual_tokens.union(planned_tokens)
            semantic_score = (len(intersection) / len(union)) * 0.5 if union else 0.0
            
            topology_score = 0.3 if actual_dir == planned_dir else (0.1 if (planned_dir and planned_dir in actual_dir) else 0.0)
            ext_score = 0.2 if actual_ext == planned_ext and actual_ext else 0.0
            
            return semantic_score + topology_score + ext_score

        for orphan in orphans:
            best_score = 0
            best_planned = None
            best_tasks = None
            
            for planned_file, tasks in missing_planned:
                sim = _compute_semantic_similarity(orphan.file_path, planned_file)
                if sim > best_score:
                    best_score = sim
                    best_planned = planned_file
                    best_tasks = tasks
                    
            if best_score >= 0.5:
                orphan.status = 'matched_semantic'
                orphan.producing_task_id = best_tasks[-1]
                missing_planned = [m for m in missing_planned if m[0] != best_planned]

        # Add remaining missing
        for planned_file, tasks in missing_planned:
            self.artifacts[planned_file] = GeneratedArtifact(
                file_path=planned_file,
                artifact_type='file',
                status='missing',
                producing_task_id=tasks[-1] if len(tasks) == 1 else 'ambiguous'
            )

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()}
        }
        
    @classmethod
    def from_dict(cls, data: dict):
        registry = cls(session_id=data.get("session_id"))
        artifacts_data = data.get("artifacts", {})
        for k, v in artifacts_data.items():
            registry.artifacts[k] = GeneratedArtifact.from_dict(v)
        return registry
