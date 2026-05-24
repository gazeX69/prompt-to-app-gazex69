from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillMetadata:
    name: str
    type: str
    language: str
    capabilities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class CommandStrategy:
    install: Optional[list[str]] = None
    build: Optional[list[str]] = None
    dev: Optional[list[str]] = None
    lint: Optional[list[str]] = None
    test: Optional[list[str]] = None

    def has_install(self) -> bool:
        return self.install is not None

    def has_build(self) -> bool:
        return self.build is not None

    def to_dict(self) -> dict:
        return {
            "install": self.install,
            "build": self.build,
            "dev": self.dev,
            "lint": self.lint,
            "test": self.test,
        }


@dataclass
class PreviewStrategy:
    host: str = "127.0.0.1"
    port: int = 3000
    readiness_patterns: list[str] = field(default_factory=lambda: [
        r"http://(?:localhost|127\.0\.0\.1):(\d+)",
        r"started",
        r"Listening",
        r"Development Server",
    ])
    check_url: Optional[str] = None
    fallback_ports: list[int] = field(default_factory=lambda: [3001, 3002, 3003])


@dataclass
class FileTarget:
    path: str
    content: str
    description: str = ""


class BaseSkill(ABC):
    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        ...

    @abstractmethod
    async def can_handle(self, context: dict) -> bool:
        ...

    @abstractmethod
    async def execute(self, context: dict) -> dict:
        ...

    def get_command_strategy(self) -> CommandStrategy:
        return CommandStrategy()

    def get_preview_strategy(self) -> PreviewStrategy:
        return PreviewStrategy()

    def get_system_prompt(self) -> str:
        return ""

    def get_project_structure(self) -> list[str]:
        return []

    def get_file_patterns(self) -> list[str]:
        return ["*"]

    def get_required_files_before_install(self) -> list[str]:
        return []

    def get_required_files_before_dev(self) -> list[str]:
        return []

    def get_generation_hints(self) -> dict:
        return {
            "requires_template": True,
            "template_name": "",
            "requires_install": True,
            "requires_build": True,
            "requires_dev_server": True,
        }

    async def get_prompt_modifiers(self) -> list[dict]:
        return []

    async def get_detection_hints(self) -> dict:
        return {}
