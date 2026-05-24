"""
Project scanning engine.

Aggregates detector signals into a structured ProjectScanResult.
Supports scanning new directories or the current workspace.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.core.scanner.detectors import (
    detect_package_manager,
    detect_framework,
    detect_language,
    detect_monorepo,
    detect_tailwind,
    detect_prisma,
    detect_docker,
    detect_ci,
    detect_has_backend,
    detect_has_frontend,
    detect_config_files,
)


@dataclass
class ProjectScanResult:
    framework: Optional[str] = None
    language: Optional[str] = None
    package_manager: Optional[str] = None
    is_monorepo: bool = False
    has_backend: bool = False
    has_frontend: bool = False
    uses_tailwind: bool = False
    uses_prisma: bool = False
    uses_docker: bool = False
    ci_systems: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "framework": self.framework,
            "language": self.language,
            "packageManager": self.package_manager,
            "isMonorepo": self.is_monorepo,
            "hasBackend": self.has_backend,
            "hasFrontend": self.has_frontend,
            "usesTailwind": self.uses_tailwind,
            "usesPrisma": self.uses_prisma,
            "usesDocker": self.uses_docker,
            "ciSystems": self.ci_systems,
            "configFiles": self.config_files,
            "capabilities": self.capabilities,
        }


def scan_project(project_path: str | Path) -> ProjectScanResult:
    path = Path(project_path).resolve()
    if not path.exists():
        return ProjectScanResult()

    framework = detect_framework(path)
    language = detect_language(path)
    package_manager = detect_package_manager(path)
    is_monorepo = detect_monorepo(path)
    uses_tailwind = detect_tailwind(path)
    uses_prisma = detect_prisma(path)
    uses_docker = detect_docker(path)
    ci_systems = detect_ci(path)
    has_backend = detect_has_backend(path)
    has_frontend = detect_has_frontend(path)
    config_files = detect_config_files(path)

    capabilities = _derive_capabilities(framework, language, has_frontend, has_backend)

    return ProjectScanResult(
        framework=framework,
        language=language,
        package_manager=package_manager,
        is_monorepo=is_monorepo,
        has_backend=has_backend,
        has_frontend=has_frontend,
        uses_tailwind=uses_tailwind,
        uses_prisma=uses_prisma,
        uses_docker=uses_docker,
        ci_systems=ci_systems,
        config_files=config_files,
        capabilities=capabilities,
    )


def _derive_capabilities(framework: str | None, language: str | None, has_frontend: bool, has_backend: bool) -> list[str]:
    caps = []
    if has_frontend:
        caps.append("frontend")
    if has_backend:
        caps.append("backend")
    if framework in ("react-vite", "react", "nextjs", "vue"):
        caps.append("spa")
    if framework in ("nextjs", "nuxt"):
        caps.append("ssr")
    if language in ("typescript",):
        caps.append("typed")
    return caps
