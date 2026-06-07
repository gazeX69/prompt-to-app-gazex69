import logging
import re
from dataclasses import dataclass, field

from backend.orchestrator.artifact_taxonomy import ArtifactCategory, ArtifactDescriptor, classify_artifact

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactRequirement:
    name: str
    artifact_type: str = "symbol"
    artifact_category: ArtifactCategory = ArtifactCategory.OTHER


@dataclass(frozen=True)
class ArtifactProduction:
    name: str
    artifact_type: str = "symbol"
    artifact_category: ArtifactCategory = ArtifactCategory.OTHER
    producing_task_id: str | None = None
    file_path: str | None = None


@dataclass
class ArtifactValidationResult:
    passed: bool
    task_id: str
    missing_artifacts: list[str] = field(default_factory=list)
    produced_artifacts: list[str] = field(default_factory=list)
    message: str = ""


class ArtifactContractRegistry:
    """
    Runtime handoff registry for semantic task artifacts.

    This registry is intentionally separate from the file-level artifact registry:
    it tracks symbols/contracts that one task proves and later tasks consume.
    """

    def __init__(self) -> None:
        self.produced_artifacts: dict[str, ArtifactProduction] = {}

    def validate_requirements(self, task) -> ArtifactValidationResult:
        required = _artifact_names(getattr(task, "requires_artifacts", []))
        logger.info("[ArtifactContract] Task %s requires: %s", task.id, ", ".join(required) or "(none)")
        missing = [name for name in required if name not in self.produced_artifacts]
        if missing:
            logger.error("[ArtifactContract] Validation failed task=%s missing=%s", task.id, ", ".join(missing))
            return ArtifactValidationResult(
                passed=False,
                task_id=task.id,
                missing_artifacts=missing,
                message=f"Task {task.id} blocked; missing artifacts: {', '.join(missing)}",
            )
        logger.info("[ArtifactContract] Validation passed task=%s", task.id)
        return ArtifactValidationResult(passed=True, task_id=task.id)

    def register_artifact(self, production: ArtifactProduction) -> None:
        self.produced_artifacts[production.name] = production
        logger.info(
            "[ArtifactContract] Registered artifact: %s task=%s file=%s",
            production.name,
            production.producing_task_id,
            production.file_path,
        )
        logger.info(
            "[ArtifactTaxonomy] category=%s artifact=%s producer=%s",
            production.artifact_category.value,
            production.name,
            production.producing_task_id,
        )

    def register_discovered_files(self, task, files: dict[str, str]) -> ArtifactValidationResult:
        declared = _artifact_names(getattr(task, "produces_artifacts", []))
        logger.info("[ArtifactContract] Task %s produces: %s", task.id, ", ".join(declared) or "(none)")
        discovered: dict[str, tuple[str, ArtifactCategory]] = {}

        for file_path, content in files.items():
            for descriptor in discover_artifact_descriptors(file_path, content):
                discovered.setdefault(descriptor.name, (file_path, descriptor.artifact_category))

        allowed = set(declared) if declared else set(discovered)
        registered: list[str] = []
        for name, (file_path, artifact_category) in discovered.items():
            if name in allowed:
                self.register_artifact(
                    ArtifactProduction(
                        name=name,
                        artifact_category=artifact_category,
                        producing_task_id=task.id,
                        file_path=file_path,
                    )
                )
                registered.append(name)

        missing = [name for name in declared if name not in discovered]
        if missing:
            logger.error("[ArtifactContract] Validation failed task=%s missing_productions=%s", task.id, ", ".join(missing))
            return ArtifactValidationResult(
                passed=False,
                task_id=task.id,
                missing_artifacts=missing,
                produced_artifacts=registered,
                message=f"Task {task.id} did not prove produced artifacts: {', '.join(missing)}",
            )

        logger.info("[ArtifactContract] Validation passed task=%s", task.id)
        return ArtifactValidationResult(passed=True, task_id=task.id, produced_artifacts=registered)


def _artifact_names(items: list[str | dict | ArtifactRequirement | ArtifactProduction]) -> list[str]:
    names: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            name = item
        elif isinstance(item, (ArtifactRequirement, ArtifactProduction)):
            name = item.name
        elif isinstance(item, dict):
            name = str(item.get("name") or "")
        else:
            name = str(item)
        name = name.strip()
        if name and name not in names:
            names.append(name)
    return names


def discover_artifact_descriptors(file_path: str, content: str) -> list[ArtifactDescriptor]:
    if not content:
        return []

    normalized_path = (file_path or "").lower()
    patterns: list[tuple[str, str]] = []
    if normalized_path.endswith((".ts", ".tsx", ".js", ".jsx")):
        patterns = [
            ("interface", r"\bexport\s+interface\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("type", r"\bexport\s+type\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("enum", r"\bexport\s+enum\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("const", r"\bexport\s+const\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("function", r"\bexport\s+function\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("class", r"\bexport\s+class\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("default_function", r"\bexport\s+default\s+function\s+([A-Za-z_][A-Za-z0-9_]*)"),
        ]
    elif normalized_path.endswith(".py"):
        patterns = [
            ("class", r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("function", r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)"),
        ]
    elif normalized_path.endswith(".php"):
        patterns = [
            ("class", r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"),
            ("function", r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)"),
        ]

    artifacts: list[ArtifactDescriptor] = []
    seen: set[str] = set()
    for declaration_kind, pattern in patterns:
        for match in re.finditer(pattern, content, flags=re.MULTILINE):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                artifacts.append(
                    ArtifactDescriptor(
                        name=name,
                        artifact_category=classify_artifact(name, declaration_kind, file_path),
                    )
                )
            if name.startswith("use") and len(name) > 3 and name[3].isupper():
                alias = name[3:]
                if alias not in seen:
                    seen.add(alias)
                    artifacts.append(ArtifactDescriptor(name=alias, artifact_category=ArtifactCategory.STORE))
    return artifacts


def discover_artifacts(file_path: str, content: str) -> list[str]:
    return [descriptor.name for descriptor in discover_artifact_descriptors(file_path, content)]
