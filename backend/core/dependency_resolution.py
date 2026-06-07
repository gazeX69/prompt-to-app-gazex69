import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.agent.tools import _safe_project_path
from backend.runtime_contract import DEPENDENCY_POLICY

logger = logging.getLogger(__name__)

DEPENDENCY_RESOLUTION_PATH = ".ai-agent/dependency_resolution.json"

FRAMEWORK_DEPENDENCIES = {
    "@types/node",
    "@types/react",
    "@types/react-dom",
    "@vitejs/plugin-react",
    "react",
    "react-dom",
    "typescript",
    "vite",
}

FEATURE_DEPENDENCIES = {
    "axios",
    "dayjs",
    "lucide-react",
    "react-router-dom",
    "uuid",
    "zustand",
}

NATIVE_REPLACEMENTS = {
    "uuid": "crypto.randomUUID()",
}

IMPORT_PATTERNS = [
    re.compile(r"""import\s+(?:type\s+)?(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]"""),
    re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
]

UUID_IMPORT_PATTERNS = [
    re.compile(r"""^\s*import\s+\{\s*v4\s+as\s+(\w+)\s*\}\s+from\s+['"]uuid['"]\s*;?\s*$""", re.MULTILINE),
    re.compile(r"""^\s*import\s+\{\s*v4\s*\}\s+from\s+['"]uuid['"]\s*;?\s*$""", re.MULTILINE),
    re.compile(r"""^\s*import\s+(\w+)\s+from\s+['"]uuid['"]\s*;?\s*$""", re.MULTILINE),
    re.compile(r"""^\s*import\s+\*\s+as\s+(\w+)\s+from\s+['"]uuid['"]\s*;?\s*$""", re.MULTILINE),
]


@dataclass(frozen=True)
class ImportRecord:
    package: str
    import_name: str
    file: str


def resolve_dependency_health(project_id: str, run_id: str | None = None, *, persist: bool = True) -> dict[str, Any]:
    project_path = _safe_project_path(project_id, run_id)
    package_data = _read_json(project_path / "package.json")
    declared = _declared_package_names(package_data or {})
    imports = _collect_external_imports(project_path)

    detected_imports: list[dict[str, str]] = []
    framework_dependencies: list[dict[str, Any]] = []
    feature_dependencies: list[dict[str, Any]] = []
    invalid_dependencies: list[dict[str, Any]] = []
    missing_dependencies: list[dict[str, Any]] = []

    blocked = set(DEPENDENCY_POLICY.get("blockedDependencies") or [])

    for record in imports:
        detected_imports.append(
            {
                "package": record.package,
                "import": record.import_name,
                "file": record.file,
            }
        )
        logger.info("[DependencyResolver] Found external import %s", record.package)

        classification = _classify_package(record.package)
        item = {
            "package": record.package,
            "classification": classification,
            "file": record.file,
            "declared": record.package in declared,
        }

        if record.package in blocked:
            invalid_dependencies.append({**item, "reason": "blocked_dependency"})
            logger.warning("[DependencyValidator] %s is blocked by dependency policy", record.package)
            continue

        if classification == "framework":
            framework_dependencies.append(item)
        elif classification == "feature":
            feature_dependencies.append(item)
        else:
            invalid_dependencies.append({**item, "reason": "unknown_external_dependency"})

        if record.package not in declared:
            missing_dependencies.append(item)
            logger.warning("[DependencyValidator] %s missing from package.json", record.package)

    repair_strategy = _build_repair_strategy(missing_dependencies, invalid_dependencies)
    for repair in repair_strategy:
        if repair.get("strategy") == "replace_native":
            logger.info(
                "[DependencyRepair] Suggested %s replacement",
                repair.get("replacement"),
            )

    report = {
        "status": _status(missing_dependencies, invalid_dependencies),
        "detected_imports": detected_imports,
        "declared_dependencies": sorted(declared),
        "missing_dependencies": _dedupe_dependency_items(missing_dependencies),
        "framework_dependencies": _dedupe_dependency_items(framework_dependencies),
        "feature_dependencies": _dedupe_dependency_items(feature_dependencies),
        "invalid_dependencies": _dedupe_dependency_items(invalid_dependencies),
        "repair_strategy": repair_strategy,
        "repair_result": "pending" if repair_strategy else "not_required",
    }

    if persist:
        _persist_report(project_path, report)
    return report


def apply_native_dependency_repair(
    project_id: str,
    run_id: str | None = None,
    *,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_path = _safe_project_path(project_id, run_id)
    current_report = report or resolve_dependency_health(project_id, run_id, persist=False)
    strategies = current_report.get("repair_strategy") or []
    native_targets = {
        item.get("dependency")
        for item in strategies
        if item.get("strategy") == "replace_native" and item.get("dependency") in NATIVE_REPLACEMENTS
    }

    changed_files: list[str] = []
    if "uuid" in native_targets:
        for source_path in _source_files(project_path):
            text = _read_text(source_path)
            if not text or "'uuid'" not in text and '"uuid"' not in text:
                continue
            repaired = _replace_uuid_import_usage(text)
            if repaired != text:
                source_path.write_text(repaired, encoding="utf-8")
                changed_files.append(source_path.relative_to(project_path).as_posix())
                logger.info("[DependencyRepair] Applied crypto.randomUUID replacement in %s", changed_files[-1])

    repaired_report = resolve_dependency_health(project_id, run_id, persist=False)
    repaired_report["repair_result"] = "applied" if changed_files else "not_applied"
    repaired_report["repair_changed_files"] = changed_files
    _persist_report(project_path, repaired_report)
    return repaired_report


def has_unresolved_feature_dependency(report: dict[str, Any]) -> bool:
    return any(
        item.get("classification") == "feature"
        for item in report.get("missing_dependencies") or []
    )


def has_unresolved_framework_dependency(report: dict[str, Any]) -> bool:
    return any(
        item.get("classification") == "framework"
        for item in report.get("missing_dependencies") or []
    )


def _build_repair_strategy(
    missing_dependencies: list[dict[str, Any]],
    invalid_dependencies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    strategy: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in missing_dependencies:
        dependency = str(item.get("package") or "")
        if not dependency or dependency in seen:
            continue
        seen.add(dependency)
        if item.get("classification") == "feature" and dependency in NATIVE_REPLACEMENTS:
            strategy.append(
                {
                    "dependency": dependency,
                    "strategy": "replace_native",
                    "replacement": NATIVE_REPLACEMENTS[dependency],
                    "status": "pending",
                }
            )
        elif item.get("classification") == "feature":
            strategy.append(
                {
                    "dependency": dependency,
                    "strategy": "add_dependency",
                    "package_json_section": "dependencies",
                    "status": "pending",
                }
            )
        elif item.get("classification") == "framework":
            strategy.append(
                {
                    "dependency": dependency,
                    "strategy": "contract_repair_required",
                    "status": "blocked",
                }
            )
    for item in invalid_dependencies:
        dependency = str(item.get("package") or "")
        if dependency and dependency not in seen:
            strategy.append(
                {
                    "dependency": dependency,
                    "strategy": "manual_review",
                    "reason": item.get("reason") or "invalid_dependency",
                    "status": "blocked",
                }
            )
    return strategy


def _status(missing_dependencies: list[dict[str, Any]], invalid_dependencies: list[dict[str, Any]]) -> str:
    if invalid_dependencies:
        return "invalid_dependency_failure"
    if missing_dependencies:
        if any(item.get("classification") == "framework" for item in missing_dependencies):
            return "framework_dependency_failure"
        return "dependency_resolution_failure"
    return "healthy"


def _replace_uuid_import_usage(text: str) -> str:
    aliases: set[str] = set()
    namespace_aliases: set[str] = set()
    if match := UUID_IMPORT_PATTERNS[0].search(text):
        aliases.add(match.group(1))
    if UUID_IMPORT_PATTERNS[1].search(text):
        aliases.add("v4")
    if match := UUID_IMPORT_PATTERNS[2].search(text):
        aliases.add(match.group(1))
    if match := UUID_IMPORT_PATTERNS[3].search(text):
        namespace_aliases.add(match.group(1))

    for pattern in UUID_IMPORT_PATTERNS:
        text = pattern.sub("", text)
    for alias in aliases:
        text = re.sub(rf"\b{re.escape(alias)}\s*\(", "crypto.randomUUID(", text)
    for alias in namespace_aliases:
        text = re.sub(rf"\b{re.escape(alias)}\.v4\s*\(", "crypto.randomUUID(", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def _collect_external_imports(project_path: Path) -> list[ImportRecord]:
    records: list[ImportRecord] = []
    seen: set[tuple[str, str]] = set()
    for source_path in _source_files(project_path):
        rel_path = source_path.relative_to(project_path).as_posix()
        for import_name in _external_imports(source_path):
            package_name = _package_name(import_name)
            if not package_name:
                continue
            key = (package_name, rel_path)
            if key in seen:
                continue
            seen.add(key)
            records.append(ImportRecord(package=package_name, import_name=import_name, file=rel_path))
    return sorted(records, key=lambda item: (item.package, item.file))


def _classify_package(package_name: str) -> str:
    if package_name in FRAMEWORK_DEPENDENCIES:
        return "framework"
    if package_name in FEATURE_DEPENDENCIES:
        return "feature"
    return "invalid"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _declared_package_names(package_data: dict[str, Any]) -> set[str]:
    dependencies = package_data.get("dependencies") if isinstance(package_data.get("dependencies"), dict) else {}
    dev_dependencies = package_data.get("devDependencies") if isinstance(package_data.get("devDependencies"), dict) else {}
    return set(dependencies) | set(dev_dependencies)


def _source_files(project_path: Path) -> list[Path]:
    source_roots = [project_path / "src", project_path / "vite.config.ts", project_path / "vite.config.js"]
    files: list[Path] = []
    for source_root in source_roots:
        if source_root.is_file() and source_root.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            files.append(source_root)
        elif source_root.is_dir():
            files.extend(
                path
                for path in source_root.rglob("*")
                if path.is_file() and path.suffix in {".ts", ".tsx", ".js", ".jsx"}
            )
    return files


def _external_imports(source_path: Path) -> set[str]:
    text = _strip_comments(_read_text(source_path) or "")
    imports: set[str] = set()
    for pattern in IMPORT_PATTERNS:
        imports.update(match.group(1) for match in pattern.finditer(text))
    return {value for value in imports if value and not _is_relative_or_asset_import(value)}


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)


def _is_relative_or_asset_import(import_name: str) -> bool:
    return (
        import_name.startswith(".")
        or import_name.startswith("/")
        or import_name.startswith("data:")
        or import_name.startswith("http:")
        or import_name.startswith("https:")
    )


def _package_name(import_name: str) -> str | None:
    if import_name.startswith("node:"):
        return None
    if import_name in {"react/jsx-runtime", "react/jsx-dev-runtime"}:
        return "react"
    parts = import_name.split("/")
    if not parts:
        return None
    if parts[0].startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _dedupe_dependency_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("package") or ""),
            str(item.get("classification") or ""),
            str(item.get("file") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _persist_report(project_path: Path, report: dict[str, Any]) -> None:
    target = project_path / DEPENDENCY_RESOLUTION_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
