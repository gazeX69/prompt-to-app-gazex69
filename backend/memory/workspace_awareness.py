from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any

from backend.agent.tools import _safe_project_path


WORKSPACE_AWARENESS_SCHEMA_VERSION = "p10.workspace_awareness.v1"
WORKSPACE_AWARENESS_RELATIVE_PATH = ".ai-agent/workspace_awareness.json"

IGNORED_DIRS = {
    ".git",
    ".orchestration",
    ".trash",
    ".vite",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
}

SOURCE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".py", ".php", ".css", ".json", ".html"}
CODE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".py", ".php"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "workspaces"


def _awareness_path(project_id: str) -> Path:
    root = _workspace_root().resolve()
    project_path = (root / project_id).resolve()
    project_path.relative_to(root)
    return project_path / WORKSPACE_AWARENESS_RELATIVE_PATH


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in IGNORED_DIRS for part in rel_parts)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_read(path: Path, limit: int = 250_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _normalize_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _resolve_source_root(project_id: str, run_id: str | None = None) -> Path:
    if run_id:
        return _safe_project_path(project_id, run_id)

    workspace = _safe_project_path(project_id)
    if (workspace / "package.json").exists() or (workspace / "src").exists():
        return workspace

    run_dirs = sorted(
        [p for p in workspace.glob("run_*") if p.is_dir()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for run_dir in run_dirs:
        if (run_dir / "package.json").exists() or (run_dir / "src").exists() or (run_dir / "index.html").exists():
            return run_dir
    return workspace


def _extract_imports(content: str, suffix: str) -> list[str]:
    patterns: list[str]
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        patterns = [
            r"import\s+(?:type\s+)?(?:[\s\S]*?)\s+from\s+['\"]([^'\"]+)['\"]",
            r"import\s+['\"]([^'\"]+)['\"]",
            r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
        ]
    elif suffix == ".py":
        patterns = [r"^import\s+([\w\.]+)", r"^from\s+([\w\.]+)\s+import"]
    elif suffix == ".php":
        patterns = [r"(?:require|include)(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]"]
    else:
        return []
    imports: list[str] = []
    for pattern in patterns:
        imports.extend(match.group(1) for match in re.finditer(pattern, content, re.MULTILINE))
    return sorted(set(imports))


def _resolve_relative_import(source_file: str, import_path: str, known_files: set[str]) -> str | None:
    if not import_path.startswith("."):
        return None
    source_dir = Path(source_file).parent
    base = (source_dir / import_path).as_posix()
    candidates = [
        base,
        f"{base}.ts",
        f"{base}.tsx",
        f"{base}.js",
        f"{base}.jsx",
        f"{base}.py",
        f"{base}/index.ts",
        f"{base}/index.tsx",
        f"{base}/index.js",
        f"{base}/index.jsx",
    ]
    normalized: list[str] = []
    for candidate in candidates:
        parts: list[str] = []
        for part in Path(candidate).parts:
            if part == ".":
                continue
            if part == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(part)
        normalized.append(Path(*parts).as_posix())
    for candidate in normalized:
        if candidate in known_files:
            return candidate
    return None


def _detect_stack(root: Path, files: list[str]) -> dict[str, Any]:
    package = _read_json(root / "package.json")
    deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
    scripts = package.get("scripts") or {}
    stack: list[str] = []
    if "react" in deps:
        stack.append("react")
    if "vite" in deps or "vite.config.ts" in files or "vite.config.js" in files:
        stack.append("vite")
    if "fastapi" in (_safe_read(root / "requirements.txt").lower()):
        stack.append("fastapi")
    if "laravel" in _safe_read(root / "composer.json").lower():
        stack.append("laravel")
    if any(path.endswith(".php") for path in files):
        stack.append("php")
    if any(path.endswith(".py") for path in files):
        stack.append("python")
    if any(path.endswith((".ts", ".tsx")) for path in files):
        stack.append("typescript")
    return {
        "stack": sorted(set(stack)) or ["unknown"],
        "package_dependencies": sorted(deps.keys()),
        "scripts": scripts,
        "config_files": [path for path in files if Path(path).name in {"package.json", "vite.config.ts", "vite.config.js", "tsconfig.json", "requirements.txt", "composer.json"}],
    }


def _detect_structure(files: list[str]) -> dict[str, Any]:
    directories = sorted({str(Path(path).parent).replace("\\", "/") for path in files if str(Path(path).parent) != "."})
    known = {
        "pages": [d for d in directories if d.endswith("pages") or "/pages" in d],
        "components": [d for d in directories if d.endswith("components") or "/components" in d],
        "services": [d for d in directories if d.endswith("services") or "/services" in d],
        "hooks": [d for d in directories if d.endswith("hooks") or "/hooks" in d],
        "stores": [d for d in directories if d.endswith("stores") or "/stores" in d or d.endswith("store")],
        "api": [d for d in directories if d.endswith("api") or "/api" in d],
        "routes": [d for d in directories if d.endswith("routes") or "/routes" in d],
        "types": [d for d in directories if d.endswith("types") or "/types" in d],
    }
    top_level = sorted({Path(path).parts[0] for path in files if Path(path).parts})
    return {"top_level": top_level, "directories": directories[:250], "conventions": known}


def _detect_patterns(root: Path, files: list[str], external_deps: list[str]) -> dict[str, Any]:
    combined = "\n".join(_safe_read(root / path, 60_000) for path in files if Path(path).suffix in CODE_EXTENSIONS)
    lower = combined.lower()
    state_management = []
    if "zustand" in external_deps or "create(" in combined and "zustand" in lower:
        state_management.append("zustand")
    if "redux" in external_deps or "@reduxjs/toolkit" in external_deps:
        state_management.append("redux")
    if "usecontext" in lower or "createcontext" in lower:
        state_management.append("react_context")
    if "usestate" in lower:
        state_management.append("react_local_state")

    api_layer = []
    if "axios" in external_deps or "from 'axios'" in combined or 'from "axios"' in combined:
        api_layer.append("axios")
    if "fetch(" in combined:
        api_layer.append("fetch")
    if "supabase" in external_deps or "createsupabaseclient" in lower or "supabase" in lower:
        api_layer.append("supabase")

    routing = []
    if "react-router-dom" in external_deps or "browserrouter" in lower or "<route" in lower:
        routing.append("react_router")
    if any(path.startswith("src/pages/") for path in files):
        routing.append("pages_directory")

    styling = []
    if "tailwind" in external_deps or "tailwind.config" in " ".join(files):
        styling.append("tailwind")
    if any(path.endswith(".module.css") for path in files):
        styling.append("css_modules")
    if any(path.endswith(".css") for path in files):
        styling.append("css")

    return {
        "state_management": sorted(set(state_management)) or ["unknown"],
        "api_layer": sorted(set(api_layer)) or ["none_detected"],
        "routing": sorted(set(routing)) or ["none_detected"],
        "styling": sorted(set(styling)) or ["none_detected"],
        "component_style": "function_components" if re.search(r"(export\s+default\s+)?function\s+[A-Z]\w+|const\s+[A-Z]\w+\s*=", combined) else "unknown",
    }


def _architecture_summary(files: list[str], dependency_graph: dict[str, list[str]], reverse_graph: dict[str, list[str]], patterns: dict[str, Any]) -> dict[str, Any]:
    entrypoints = [
        path for path in files
        if path in {"src/main.tsx", "src/main.jsx", "src/App.tsx", "src/App.jsx", "index.html", "main.py", "app.py", "index.php"}
    ]
    layers = {
        "ui": [path for path in files if any(part in path for part in ["components/", "pages/", "App.tsx", "App.jsx"])],
        "state": [path for path in files if any(part in path.lower() for part in ["store", "stores/", "hooks/use"])],
        "api": [path for path in files if any(part in path.lower() for part in ["service", "api/", "client"])],
        "types": [path for path in files if "type" in path.lower() or path.endswith(".d.ts")],
    }
    critical_files = sorted(
        reverse_graph.keys(),
        key=lambda file: len(reverse_graph.get(file, [])),
        reverse=True,
    )[:10]
    flow = ["UI"]
    if patterns.get("state_management") and patterns["state_management"] != ["unknown"]:
        flow.append("State")
    if patterns.get("api_layer") and patterns["api_layer"] != ["none_detected"]:
        flow.append("API")
    flow.append("Runtime")
    return {
        "entrypoints": entrypoints,
        "layers": {key: value[:80] for key, value in layers.items() if value},
        "critical_files": [{"file": path, "dependents": len(reverse_graph.get(path, []))} for path in critical_files],
        "flow": flow,
        "dependency_edges": sum(len(deps) for deps in dependency_graph.values()),
    }


def _impact_analysis(prompt: str, files: list[str], reverse_graph: dict[str, list[str]], architecture: dict[str, Any]) -> dict[str, Any]:
    text = (prompt or "").lower()
    intent_terms = {
        "auth": ["auth", "login", "role", "permission", "token"],
        "cart": ["cart", "keranjang"],
        "checkout": ["checkout", "payment", "order", "pesanan"],
        "product": ["product", "produk", "catalog", "katalog"],
        "wishlist": ["wishlist", "favorite", "favorit"],
        "dashboard": ["dashboard", "analytics", "report", "laporan"],
    }
    domains = [domain for domain, terms in intent_terms.items() if any(term in text for term in terms)]
    candidates: set[str] = set()
    for file in files:
        lower_file = file.lower()
        if any(domain in lower_file for domain in domains):
            candidates.add(file)
    if not candidates and domains:
        for layer in architecture.get("layers", {}).values():
            candidates.update(layer[:5])
    affected = set(candidates)
    for file in list(candidates):
        affected.update(reverse_graph.get(file, []))
    risk = "low"
    if len(affected) >= 8:
        risk = "high"
    elif len(affected) >= 3:
        risk = "medium"
    return {
        "prompt_domains": domains,
        "candidate_files": sorted(candidates)[:25],
        "affected_files": sorted(affected)[:50],
        "affected_count": len(affected),
        "risk": risk,
        "confidence": 0.72 if domains else 0.45,
    }


class WorkspaceAwareness:
    @staticmethod
    def load(project_id: str) -> dict[str, Any] | None:
        path = _awareness_path(project_id)
        if not path.exists():
            return None
        data = _read_json(path)
        return data or None

    @staticmethod
    def save(project_id: str, awareness: dict[str, Any]) -> dict[str, Any]:
        path = _awareness_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        awareness["schema_version"] = WORKSPACE_AWARENESS_SCHEMA_VERSION
        awareness["project_id"] = project_id
        awareness["updated_at"] = _utc_now()
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(awareness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return awareness

    @staticmethod
    def scan(project_id: str, run_id: str | None = None, prompt: str | None = None) -> dict[str, Any]:
        root = _resolve_source_root(project_id, run_id)
        root.mkdir(parents=True, exist_ok=True)
        files: list[str] = []
        for path in root.rglob("*"):
            if _is_ignored(path, root) or not path.is_file():
                continue
            if path.suffix.lower() in SOURCE_EXTENSIONS or path.name in {"package.json", "requirements.txt", "composer.json"}:
                files.append(_normalize_rel(path, root))
        files = sorted(files)
        known_files = set(files)
        stack = _detect_stack(root, files)
        structure = _detect_structure(files)

        dependency_graph: dict[str, list[str]] = {}
        external_imports: set[str] = set()
        for file in files:
            path = root / file
            if path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            imports = _extract_imports(_safe_read(path), path.suffix.lower())
            resolved: list[str] = []
            for imported in imports:
                target = _resolve_relative_import(file, imported, known_files)
                if target:
                    resolved.append(target)
                elif not imported.startswith("."):
                    external_imports.add(imported.split("/")[0] if not imported.startswith("@") else "/".join(imported.split("/")[:2]))
            dependency_graph[file] = sorted(set(resolved))

        reverse_graph = {file: [] for file in dependency_graph}
        for source, targets in dependency_graph.items():
            for target in targets:
                reverse_graph.setdefault(target, []).append(source)
        reverse_graph = {key: sorted(set(value)) for key, value in reverse_graph.items()}

        patterns = _detect_patterns(root, files, stack.get("package_dependencies", []))
        architecture = _architecture_summary(files, dependency_graph, reverse_graph, patterns)
        impact = _impact_analysis(prompt or "", files, reverse_graph, architecture)

        awareness = {
            "schema_version": WORKSPACE_AWARENESS_SCHEMA_VERSION,
            "project_id": project_id,
            "source_root": str(root.resolve()),
            "run_id": run_id,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "maturity": {
                "level_1_file_awareness": bool(files and stack.get("stack")),
                "level_2_structure_awareness": bool(structure.get("directories") or structure.get("top_level")),
                "level_3_dependency_awareness": bool(dependency_graph),
                "level_4_pattern_awareness": bool(patterns),
                "level_5_impact_awareness": bool(impact),
                "level_6_architecture_explanation": bool(architecture),
            },
            "files": {
                "total": len(files),
                "important": [path for path in files if Path(path).name in {"package.json", "vite.config.ts", "App.tsx", "main.tsx", "requirements.txt"}][:50],
                "all": files[:500],
            },
            "stack": stack,
            "structure": structure,
            "dependencies": {
                "graph": dependency_graph,
                "reverse_graph": reverse_graph,
                "external_imports": sorted(external_imports),
            },
            "patterns": patterns,
            "architecture": architecture,
            "impact_analysis": impact,
            "chain": [
                "level_1_file_awareness",
                "level_2_structure_awareness",
                "level_3_dependency_awareness",
                "level_4_pattern_awareness",
                "level_5_impact_awareness",
                "level_6_architecture_explanation",
            ],
        }
        return WorkspaceAwareness.save(project_id, awareness)

    @staticmethod
    def build_context(project_id: str, run_id: str | None = None, prompt: str | None = None) -> str:
        awareness = WorkspaceAwareness.scan(project_id, run_id=run_id, prompt=prompt)
        stack = ", ".join(awareness["stack"].get("stack") or [])
        top_dirs = ", ".join(awareness["structure"].get("top_level") or [])
        patterns = awareness.get("patterns") or {}
        impact = awareness.get("impact_analysis") or {}
        architecture = awareness.get("architecture") or {}
        return (
            "=== WORKSPACE AWARENESS ===\n"
            "Epistemic rule: Workspace Awareness is derived from a lightweight scan and carries confidence, not certainty.\n"
            f"Source root: {awareness.get('source_root')}\n"
            f"Stack: {stack}\n"
            f"Files scanned: {awareness['files'].get('total')}\n"
            f"Top-level structure: {top_dirs or 'none'}\n"
            f"State management pattern: {', '.join(patterns.get('state_management') or [])}\n"
            f"API pattern: {', '.join(patterns.get('api_layer') or [])}\n"
            f"Routing pattern: {', '.join(patterns.get('routing') or [])}\n"
            f"Architecture flow: {' -> '.join(architecture.get('flow') or [])}\n"
            f"Impact risk for this prompt: {impact.get('risk')} ({impact.get('affected_count', 0)} files)\n"
            f"Candidate files: {', '.join(impact.get('candidate_files') or []) or 'none'}\n"
            "Rules:\n"
            "- Place new files in the existing structure when possible.\n"
            "- Follow detected state/API/routing/styling patterns; do not introduce competing libraries without explicit need.\n"
            "- Prefer low-ripple files for modifications and preserve entrypoints unless the plan requires wiring.\n"
            "=== END WORKSPACE AWARENESS ==="
        )

    @staticmethod
    def describe(project_id: str) -> dict[str, Any]:
        awareness = WorkspaceAwareness.load(project_id)
        if not awareness:
            awareness = WorkspaceAwareness.scan(project_id)
        architecture = awareness.get("architecture") or {}
        patterns = awareness.get("patterns") or {}
        summary = (
            f"Workspace memakai stack {', '.join(awareness.get('stack', {}).get('stack') or ['unknown'])}. "
            f"Struktur utama: {', '.join(awareness.get('structure', {}).get('top_level') or ['belum terdeteksi'])}. "
            f"Flow arsitektur: {' -> '.join(architecture.get('flow') or ['belum terdeteksi'])}. "
            f"State/API pattern: {', '.join(patterns.get('state_management') or [])} / {', '.join(patterns.get('api_layer') or [])}."
        )
        return {
            "workspace_awareness": awareness,
            "summary": summary,
            "confidence": 0.8 if awareness.get("files", {}).get("total", 0) else 0.45,
            "source": WORKSPACE_AWARENESS_RELATIVE_PATH,
        }
