from pydantic import BaseModel, Field


class DiscoveryNode(BaseModel):
    id: str
    question: str
    field: str
    children: list[str] = Field(default_factory=list)
    project_type: str | None = None
    answer_type: str = "string"
    answer_aliases: dict[str, object] = Field(default_factory=dict)
    transitions: dict[str, str] = Field(default_factory=dict)
    default_next: str | None = None
    terminal: bool = False


class DiscoverySessionState(BaseModel):
    session_id: str
    root_node: str
    current_node: str | None = None
    answers: dict[str, object] = Field(default_factory=dict)
    draft_state: dict[str, object] = Field(default_factory=dict)
    complete: bool = False


class DiscoveryTurn(BaseModel):
    session_id: str
    current_node: str | None = None
    question: str | None = None
    field: str | None = None
    answers: dict[str, object] = Field(default_factory=dict)
    draft_state: dict[str, object] = Field(default_factory=dict)
    complete: bool = False
