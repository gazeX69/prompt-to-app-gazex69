import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from backend.agent.tools import _safe_project_path
from backend.runtime_contract import RuntimeErrorCode, classify_dependency_import


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_TEMPLATE = PROJECT_ROOT / "templates" / "react-vite-ts"

PROTECTED_CONTRACT_FILES = {
    "package.json",
    "tsconfig.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "vite.config.ts",
    "index.html",
    "src/main.tsx",
    "src/vite-env.d.ts",
}

ENTRYPOINT_FILES = set()

RESTORABLE_CONTRACT_FILES = PROTECTED_CONTRACT_FILES | ENTRYPOINT_FILES


@dataclass
class ContractReport:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return "React/Vite contract passed"
        return "; ".join(self.errors)


def validate_react_vite_contract(project_id: str, run_id: str | None = None) -> ContractReport:
    project_path = _safe_project_path(project_id, run_id)
    errors: list[str] = []
    warnings: list[str] = []

    required = sorted(RESTORABLE_CONTRACT_FILES | {"src/App.tsx", "src/index.css"})
    for rel in required:
        if not (project_path / rel).exists():
            errors.append(f"{RuntimeErrorCode.E_REACT_ROOT_MISSING.value}:{rel}" if rel.startswith("src/") else f"{RuntimeErrorCode.E_CONTRACT_INVALID.value}:{rel}")

    package_data = _read_json(project_path / "package.json", errors, "package_json_invalid")
    if package_data:
        scripts = package_data.get("scripts") or {}
        if scripts.get("dev") != "vite":
            errors.append(f"{RuntimeErrorCode.E_CONTRACT_INVALID.value}:package_scripts_dev")
        if scripts.get("build") != "tsc -b && vite build":
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:build_script_must_use_tsc_b")
        if "preview" not in scripts:
            errors.append(f"{RuntimeErrorCode.E_CONTRACT_INVALID.value}:package_scripts_preview")

        deps = package_data.get("dependencies") or {}
        dev_deps = package_data.get("devDependencies") or {}
        for dep in ("react", "react-dom"):
            if dep not in deps:
                errors.append(f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:{dep}")
        for dep in ("@vitejs/plugin-react", "typescript", "vite", "@types/react", "@types/react-dom", "@types/node"):
            if dep not in dev_deps:
                errors.append(f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:{dep}")

    tsconfig = _read_json(project_path / "tsconfig.json", errors, "tsconfig_json_invalid")
    if tsconfig:
        refs = tsconfig.get("references")
        expected_refs = [{"path": "./tsconfig.app.json"}, {"path": "./tsconfig.node.json"}]
        if tsconfig.get("files") != [] or refs != expected_refs:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:root_references")
        if tsconfig.get("compilerOptions", {}).get("noEmit") is True:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:root_no_emit_with_references")

    app_config = _read_json(project_path / "tsconfig.app.json", errors, "tsconfig_app_invalid")
    if app_config:
        options = app_config.get("compilerOptions") or {}
        if options.get("moduleResolution") != "bundler":
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:app_module_resolution")
        if options.get("jsx") != "react-jsx":
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:app_jsx")
        if options.get("noEmit") is not True:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:app_no_emit")
        if app_config.get("include") != ["src"]:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:app_include")

    node_config = _read_json(project_path / "tsconfig.node.json", errors, "tsconfig_node_invalid")
    if node_config:
        options = node_config.get("compilerOptions") or {}
        if options.get("moduleResolution") != "bundler":
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:node_module_resolution")
        if options.get("noEmit") is not True:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:node_no_emit")
        if options.get("types") != ["node"]:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:node_types")
        if node_config.get("include") != ["vite.config.ts"]:
            errors.append(f"{RuntimeErrorCode.E_TS_REFERENCE_INVALID.value}:node_include")

    vite_text = _read_text(project_path / "vite.config.ts")
    if vite_text is not None:
        if "defineConfig" not in vite_text or "@vitejs/plugin-react" not in vite_text or "react()" not in vite_text:
            errors.append(f"{RuntimeErrorCode.E_VITE_CONFIG.value}:missing_react_plugin")

    html_text = _read_text(project_path / "index.html")
    if html_text is not None:
        if 'id="root"' not in html_text and "id='root'" not in html_text:
            errors.append(f"{RuntimeErrorCode.E_REACT_ROOT_MISSING.value}:index_html")
        if "/src/main.tsx" not in html_text:
            errors.append(f"{RuntimeErrorCode.E_REACT_ROOT_MISSING.value}:index_html_script")

    main_text = _read_text(project_path / "src" / "main.tsx")
    if main_text is not None:
        if "react-dom/client" not in main_text or "createRoot" not in main_text:
            errors.append(f"{RuntimeErrorCode.E_REACT_ROOT_MISSING.value}:create_root")
        if "getElementById('root')" not in main_text and 'getElementById("root")' not in main_text:
            errors.append(f"{RuntimeErrorCode.E_REACT_ROOT_MISSING.value}:root_lookup")
        if "<App" not in main_text:
            errors.append(f"{RuntimeErrorCode.E_REACT_ROOT_MISSING.value}:app_render")

    declared_packages = _declared_package_names(package_data or {})
    for source_path in _source_files(project_path):
        rel_path = source_path.relative_to(project_path).as_posix()
        for import_name in _external_imports(source_path):
            package_name = _package_name(import_name)
            if not package_name:
                continue
            dependency_error = classify_dependency_import(package_name, declared_packages)
            if dependency_error:
                errors.append(f"{dependency_error.value}:{package_name}:{rel_path}")

    return ContractReport(passed=not errors, errors=errors, warnings=warnings)


def restore_canonical_react_vite_contract(
    project_id: str,
    run_id: str | None = None,
    files: set[str] | None = None,
) -> list[str]:
    project_path = _safe_project_path(project_id, run_id)
    targets = files or RESTORABLE_CONTRACT_FILES
    restored: list[str] = []

    for rel in sorted(targets):
        src = CANONICAL_TEMPLATE / rel
        if not src.exists():
            continue
        dst = project_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored.append(rel)

    return restored


def classify_react_vite_failure(stdout: str, stderr: str) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if "ts6310" in text or "referenced project" in text or "tsconfig" in text:
        return RuntimeErrorCode.E_TS_REFERENCE_INVALID.value
    if "cannot find type definition file for 'node'" in text or "cannot find type definition file for \"node\"" in text:
        return RuntimeErrorCode.E_DEPENDENCY_MISSING.value
    if "cannot find module '@vitejs/plugin-react'" in text or "failed to load config" in text:
        return RuntimeErrorCode.E_VITE_CONFIG.value
    if "could not resolve entry module" in text or "src/main.tsx" in text and "does not exist" in text:
        return RuntimeErrorCode.E_REACT_ROOT_MISSING.value
    if "createRoot" in text or "getelementbyid" in text or "#root" in text:
        return RuntimeErrorCode.E_REACT_ROOT_MISSING.value
    if "expected \">\"" in text or "unexpected token" in text or "transform failed" in text:
        return RuntimeErrorCode.E_BUILD_FAILURE.value
    if "failed to resolve import" in text or "module not found" in text or "cannot resolve" in text:
        return RuntimeErrorCode.E_IMPORT_RESOLUTION.value
    return RuntimeErrorCode.E_BUILD_FAILURE.value


def _read_json(path: Path, errors: list[str], error_code: str) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        error = RuntimeErrorCode.E_TS_REFERENCE_INVALID if error_code.startswith("tsconfig") else RuntimeErrorCode.E_CONTRACT_INVALID
        errors.append(f"{error.value}:{exc.msg}")
        return None


def classify_declared_import(package_name: str, declared_packages: set[str]) -> str | None:
    code = classify_dependency_import(package_name, declared_packages)
    return code.value if code else None


IMPORT_PATTERNS = [
    re.compile(r"""import\s+(?:type\s+)?(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]"""),
    re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),
]


def _declared_package_names(package_data: dict) -> set[str]:
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
