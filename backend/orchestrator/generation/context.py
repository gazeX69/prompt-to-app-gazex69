from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerationContext:
    req: Any
    run_id: str | None = None
    generation_id: str | None = None
    skill_name: str | None = None
    skill: Any = None
    route: Any = None
    project_action: dict[str, Any] | None = None
    project_state: dict[str, Any] | None = None
    workspace_awareness: dict[str, Any] | None = None
    change_scope: dict[str, Any] | None = None
    cbr_context: str = ""
    generation_signature: Any = None
    generation_scope: dict[str, Any] | None = None
    task_graph: Any = None
    session_id: str | None = None
    orchestration_session: Any = None
    project_map: Any = None
    cmd_strategy: Any = None
    metrics: dict[str, Any] = field(default_factory=dict)
    written: list[str] = field(default_factory=list)
