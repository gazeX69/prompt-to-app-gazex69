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
    enabled_skills: Optional[list[str]] = Field(default=None, description="Restrict routing to these skills")


class GeneratedFile(BaseModel):
    path: str
    content: str


class GenerateResponse(BaseModel):
    success: bool
    project_id: str
    files_written: list[str] = []
    repair_attempts: int = 0
    error: Optional[str] = None
    accepted: bool = False
    status: Optional[str] = None
    generation_id: Optional[str] = None
    status_endpoint: Optional[str] = None
    message: Optional[str] = None


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


# ── Skill System Schemas ──────────────────────────────────────────

class SkillMetaSchema(BaseModel):
    name: str
    type: str
    language: str
    capabilities: list[str] = []
    tags: list[str] = []
    description: str = ""


class ScanRequest(BaseModel):
    project_path: str


class ScanResultSchema(BaseModel):
    framework: Optional[str] = None
    language: Optional[str] = None
    packageManager: Optional[str] = None
    isMonorepo: bool = False
    hasBackend: bool = False
    hasFrontend: bool = False
    usesTailwind: bool = False
    usesPrisma: bool = False
    usesDocker: bool = False
    ciSystems: list[str] = []
    configFiles: list[str] = []
    capabilities: list[str] = []


class RouteResultSchema(BaseModel):
    primary: str = "none"
    activated: list[str] = []
    fallback_count: int = 0


class DiagnosticSchema(BaseModel):
    category: str
    message: str
    source: str
    line: Optional[int] = None
    file: Optional[str] = None
    code: Optional[str] = None
    suggestion: Optional[str] = None
