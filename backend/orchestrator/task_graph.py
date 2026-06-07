from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class TaskStatus(Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ValidationContract:
    success_criteria: list[str] = field(default_factory=list)
    runtime_proof_required: bool = False
    artifact_proof_required: bool = False
    verification_method: str = "llm" # or 'playwright', 'grep', 'http'
    timeout_ms: int = 15000

@dataclass
class PatchOperation:
    operation_type: str
    target_file: str
    target_symbol: Optional[str] = None
    insertion_strategy: str = "append"
    expected_side_effects: list[str] = field(default_factory=list)
    dependency_requirements: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "operation_type": self.operation_type,
            "target_file": self.target_file,
            "target_symbol": self.target_symbol,
            "insertion_strategy": self.insertion_strategy,
            "expected_side_effects": self.expected_side_effects,
            "dependency_requirements": self.dependency_requirements
        }

@dataclass
class ExecutionTask:
    id: str
    title: str
    description: str
    affected_files: list[str] = field(default_factory=list)
    allowed_write_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    produces_artifacts: list[str] = field(default_factory=list)
    requires_artifacts: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    validation_contract: ValidationContract = field(default_factory=ValidationContract)
    error_msg: Optional[str] = None
    created_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    logs: list[str] = field(default_factory=list)
    validation_artifacts: dict[str, str] = field(default_factory=dict)
    proposed_artifacts: dict[str, str] = field(default_factory=dict)
    patches: list[PatchOperation] = field(default_factory=list)
    
    def add_log(self, msg: str):
        self.logs.append(msg)
        
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "affected_files": self.affected_files,
            "allowed_write_paths": self.allowed_write_paths,
            "forbidden_paths": self.forbidden_paths,
            "dependencies": self.dependencies,
            "produces_artifacts": self.produces_artifacts,
            "requires_artifacts": self.requires_artifacts,
            "status": self.status.value,
            "error_msg": self.error_msg,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "logs": self.logs,
            "validation_artifacts": self.validation_artifacts,
            "validation_contract": {
                "success_criteria": self.validation_contract.success_criteria,
                "runtime_proof_required": self.validation_contract.runtime_proof_required,
                "artifact_proof_required": self.validation_contract.artifact_proof_required,
                "verification_method": self.validation_contract.verification_method,
                "timeout_ms": self.validation_contract.timeout_ms
            },
            "patches": [p.to_dict() for p in self.patches]
        }

class TaskGraph:
    def __init__(self):
        self.tasks: dict[str, ExecutionTask] = {}
        
    def to_dict(self):
        return {
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()}
        }
        
    def add_task(self, task: ExecutionTask):
        self.tasks[task.id] = task
        
    def get_task(self, task_id: str) -> Optional[ExecutionTask]:
        return self.tasks.get(task_id)

    def mark_blocked_tasks(self):
        """Update tasks to BLOCKED if their dependencies are not COMPLETED."""
        for task in self.tasks.values():
            if task.status in (TaskStatus.PENDING, TaskStatus.BLOCKED):
                is_blocked = False
                for dep_id in task.dependencies:
                    dep = self.tasks.get(dep_id)
                    if not dep or dep.status != TaskStatus.COMPLETED:
                        is_blocked = True
                        break
                
                if is_blocked:
                    task.status = TaskStatus.BLOCKED
                elif task.status == TaskStatus.BLOCKED:
                    task.status = TaskStatus.PENDING

    def get_next_runnable_tasks(self) -> list[ExecutionTask]:
        """Return tasks that are PENDING and whose dependencies are met."""
        self.mark_blocked_tasks()
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]

    def has_pending_tasks(self) -> bool:
        return any(t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in self.tasks.values())
        
    def has_failed_tasks(self) -> bool:
        return any(t.status == TaskStatus.FAILED for t in self.tasks.values())

class TaskExecutor:
    """
    Executes the TaskGraph strictly sequentially (Phase 1 constraint).
    """
    def __init__(self, graph: TaskGraph, artifact_registry=None):
        self.graph = graph
        self.artifact_registry = artifact_registry

    async def execute_all(self, execution_callback):
        """
        Traverses the graph topologically.
        execution_callback(task: ExecutionTask) -> bool (success)
        """
        while self.graph.has_pending_tasks():
            if self.graph.has_failed_tasks():
                print("[TaskExecutor] Aborting remaining tasks due to failure in graph.")
                break
                
            runnable = self.graph.get_next_runnable_tasks()
            if not runnable:
                # If there are pending tasks but none are runnable, we have a deadlock or unfulfilled dependency
                pending = [t.id for t in self.graph.tasks.values() if t.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED)]
                print(f"[TaskExecutor] Deadlock detected! Blocked tasks: {pending}")
                break
                
            # STRICT SEQUENTIAL EXECUTION: take only the first one
            task = runnable[0]
            if self.artifact_registry is not None and getattr(task, "requires_artifacts", None):
                result = self.artifact_registry.validate_requirements(task)
                if not result.passed:
                    task.status = TaskStatus.FAILED
                    task.error_msg = result.message
                    task.add_log("[ArtifactContract] Missing artifacts:")
                    for artifact in result.missing_artifacts:
                        task.add_log(f"- {artifact}")
                    task.add_log(f"[ArtifactContract] Task {task.id} blocked")
                    break
            task.status = TaskStatus.RUNNING
            
            import time
            task.started_at = time.time()
            try:
                # Execute the callback which will handle generation and validation
                success = await execution_callback(task)
                task.completed_at = time.time()
                if success:
                    task.status = TaskStatus.COMPLETED
                else:
                    task.status = TaskStatus.FAILED
            except Exception as e:
                task.completed_at = time.time()
                task.status = TaskStatus.FAILED
                task.error_msg = str(e)
                task.add_log(f"CRASH: {e}")
                print(f"[TaskExecutor] Task {task.id} crashed: {e}")
                
        return not self.graph.has_failed_tasks()
