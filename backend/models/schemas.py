from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ProjectType(str, Enum):
    REACT = "react"
    VITE_REACT = "vite-react"
    VITE_REACT_TAILWIND = "vite-react-tailwind"
    VANILLA = "vanilla"


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=5, description="What to build")
    project_id: str = Field(default="project-001", description="Workspace project folder name")
    project_type: ProjectType = Field(default=ProjectType.VITE_REACT_TAILWIND)
    auto_repair: bool = Field(default=True, description="Enable self-repair loop on build errors")
    max_repair_attempts: int = Field(default=3, ge=1, le=5)


class GeneratedFile(BaseModel):
    path: str
    content: str


class GenerateResponse(BaseModel):
    success: bool
    project_id: str
    files_written: list[str] = []
    repair_attempts: int = 0
    error: Optional[str] = None


class ExecuteRequest(BaseModel):
    project_id: str
    command: str = Field(..., description="Command to run: install | dev | build")


class ExecuteResponse(BaseModel):
    success: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    error: Optional[str] = None


class RepairRequest(BaseModel):
    project_id: str
    build_error: str
    project_type: ProjectType = ProjectType.VITE_REACT_TAILWIND
