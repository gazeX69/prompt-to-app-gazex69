import json
from dataclasses import dataclass, field
from pathlib import Path
import time
import os
from backend.sandbox.executor import _safe_project_path
from backend.orchestrator.project_mapper import ProjectMap
from backend.orchestrator.task_graph import TaskGraph

@dataclass
class OrchestrationSession:
    session_id: str
    project_id: str
    run_id: str
    skill_name: str
    project_map: ProjectMap
    task_graph: TaskGraph
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "active"

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "skill_name": self.skill_name,
            "project_map": self.project_map.to_dict(),
            "task_graph": self.task_graph.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status
        }
        
    @classmethod
    def from_dict(cls, data: dict):
        pmap_data = data.get("project_map", {})
        pmap = ProjectMap(
            project_id=pmap_data.get("project_id"),
            run_id=pmap_data.get("run_id"),
            ecosystem=pmap_data.get("ecosystem"),
            runtime_type=pmap_data.get("runtime_type"),
            frameworks=pmap_data.get("frameworks", []),
            entrypoints=pmap_data.get("entrypoints", []),
            modules=pmap_data.get("modules", []),
            dependencies=pmap_data.get("dependencies", {}),
            risks=pmap_data.get("risks", []),
            missing_components=pmap_data.get("missing_components", [])
        )
        
        tgraph = TaskGraph()
        tgraph_data = data.get("task_graph", {}).get("tasks", {})
        from backend.orchestrator.task_graph import ExecutionTask, TaskStatus, ValidationContract
        for t_id, t_data in tgraph_data.items():
            vc_data = t_data.get("validation_contract", {})
            vc = ValidationContract(
                success_criteria=vc_data.get("success_criteria", []),
                runtime_proof_required=vc_data.get("runtime_proof_required", False),
                artifact_proof_required=vc_data.get("artifact_proof_required", False),
                verification_method=vc_data.get("verification_method", "llm"),
                timeout_ms=vc_data.get("timeout_ms", 15000)
            )
            task = ExecutionTask(
                id=t_data.get("id"),
                title=t_data.get("title"),
                description=t_data.get("description"),
                affected_files=t_data.get("affected_files", []),
                allowed_write_paths=t_data.get("allowed_write_paths", []),
                forbidden_paths=t_data.get("forbidden_paths", []),
                dependencies=t_data.get("dependencies", []),
                status=TaskStatus(t_data.get("status", "pending")),
                validation_contract=vc,
                error_msg=t_data.get("error_msg"),
                created_at=t_data.get("created_at"),
                started_at=t_data.get("started_at"),
                completed_at=t_data.get("completed_at"),
                logs=t_data.get("logs", []),
                validation_artifacts=t_data.get("validation_artifacts", {}),
                proposed_artifacts=t_data.get("proposed_artifacts", {})
            )
            tgraph.add_task(task)
            
        return cls(
            session_id=data.get("session_id"),
            project_id=data.get("project_id"),
            run_id=data.get("run_id"),
            skill_name=data.get("skill_name"),
            project_map=pmap,
            task_graph=tgraph,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            status=data.get("status")
        )

class SessionPersistence:
    """
    Handles deterministic serialization and persistence of the orchestration state.
    Snapshots are saved to the project directory under .orchestration/
    """
    
    @staticmethod
    def get_session_dir(project_id: str) -> Path:
        base_path = _safe_project_path(project_id, "latest")
        session_dir = base_path / ".orchestration"
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    @staticmethod
    def save_snapshot(session: OrchestrationSession):
        session.updated_at = time.time()
        session_dir = SessionPersistence.get_session_dir(session.project_id)
        snapshot_path = session_dir / f"{session.session_id}.json"
        
        # We use an atomic write approach
        temp_path = snapshot_path.with_suffix('.tmp')
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2)
            
        # Replace atomically (handles Windows constraints properly with os.replace)
        os.replace(temp_path, snapshot_path)

    @staticmethod
    def save_artifacts(project_id: str, registry):
        session_dir = SessionPersistence.get_session_dir(project_id)
        snapshot_path = session_dir / f"{registry.session_id}.artifacts.json"
        
        temp_path = snapshot_path.with_suffix('.tmp')
        with open(temp_path, "w", encoding="utf-8") as f:
            import json
            json.dump(registry.to_dict(), f, indent=2)
            
        import os
        os.replace(temp_path, snapshot_path)

    @staticmethod
    def load_snapshot(project_id: str, session_id: str) -> OrchestrationSession:
        """
        Loads a snapshot from disk into a raw dict for read-only inspection.
        Crash Recovery Phase 1 constraint: READ-ONLY load.
        """
        session_dir = SessionPersistence.get_session_dir(project_id)
        snapshot_path = session_dir / f"{session_id}.json"
        
        if not snapshot_path.exists():
            raise FileNotFoundError(f"No orchestration session found for {session_id}")
            
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return OrchestrationSession.from_dict(data)
