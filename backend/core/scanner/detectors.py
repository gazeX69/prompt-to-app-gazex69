"""
Individual file-system based detectors for frameworks, languages, and tools.

Each detector is a standalone function that takes a project path and returns
a boolean or extracted value. This keeps detection logic composable and testable.
"""

import json
import os
from pathlib import Path


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def detect_package_manager(project_path: Path) -> str | None:
    signals = {
        "pnpm": project_path / "pnpm-lock.yaml",
        "yarn": project_path / "yarn.lock",
        "npm": project_path / "package-lock.json",
        "composer": project_path / "composer.lock",
        "pip": project_path / "requirements.txt",
        "pipenv": project_path / "Pipfile",
        "poetry": project_path / "pyproject.toml",
    }
    for manager, lockfile in signals.items():
        if lockfile.exists():
            return manager
    if (project_path / "package.json").exists():
        return "npm"
    if (project_path / "composer.json").exists():
        return "composer"
    return None


def detect_framework(project_path: Path) -> str | None:
    pkg = project_path / "package.json"
    composer = project_path / "composer.json"

    if pkg.exists():
        data = _read_json(pkg)
        if data:
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "next" in deps:
                return "nextjs"
            if "react" in deps and "vite" in deps:
                return "react-vite"
            if "react" in deps:
                return "react"
            if "vue" in deps:
                return "vue"
            if "@nestjs/core" in deps:
                return "nestjs"
            if "express" in deps:
                return "express"
            if "nuxt" in deps:
                return "nuxt"

    if composer.exists():
        data = _read_json(composer)
        if data:
            req = data.get("require", {})
            if "laravel/framework" in req or "laravel/laravel" in req:
                return "laravel"
            if "symfony" in req.get("php", ""):
                return "symfony"

    if (project_path / "vite.config.ts").exists() or (project_path / "vite.config.js").exists():
        return "vite"
    if (project_path / "next.config.js").exists() or (project_path / "next.config.ts").exists():
        return "nextjs"
    if (project_path / "vue.config.js").exists():
        return "vue"

    return None


def detect_language(project_path: Path) -> str | None:
    signals = {
        "php": lambda p: p.suffix == ".php",
        "python": lambda p: p.suffix == ".py",
        "typescript": lambda p: p.suffix in (".ts", ".tsx"),
        "javascript": lambda p: p.suffix in (".js", ".jsx", ".mjs"),
        "rust": lambda p: p.suffix == ".rs",
        "go": lambda p: p.suffix == ".go",
        "java": lambda p: p.suffix == ".java",
        "ruby": lambda p: p.suffix == ".rb",
    }

    if (project_path / "tsconfig.json").exists():
        return "typescript"
    if (project_path / "composer.json").exists():
        return "php"
    if (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
        return "python"
    if (project_path / "go.mod").exists():
        return "go"
    if (project_path / "Cargo.toml").exists():
        return "rust"

    # Walk a limited depth to find source files
    try:
        for entry in list(project_path.iterdir())[:50]:
            for candidate in [entry] + (list(entry.rglob("*"))[:200] if entry.is_dir() else []):
                for lang, check in signals.items():
                    if check(candidate):
                        return lang
    except Exception:
        pass
    return None


def detect_monorepo(project_path: Path) -> bool:
    pkg = project_path / "package.json"
    if pkg.exists():
        data = _read_json(pkg)
        if data:
            workspaces = data.get("workspaces", [])
            if workspaces:
                return True
    if (project_path / "lerna.json").exists():
        return True
    if (project_path / "pnpm-workspace.yaml").exists():
        return True
    return False


def detect_tailwind(project_path: Path) -> bool:
    config_names = [
        "tailwind.config.js", "tailwind.config.ts",
        "tailwind.config.cjs", "tailwind.config.mjs",
    ]
    for name in config_names:
        if (project_path / name).exists():
            return True
    return False


def detect_prisma(project_path: Path) -> bool:
    prisma_dir = project_path / "prisma"
    if prisma_dir.exists() and (prisma_dir / "schema.prisma").exists():
        return True
    return False


def detect_docker(project_path: Path) -> bool:
    return any((project_path / name).exists() for name in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"])


def detect_ci(project_path: Path) -> list[str]:
    found = []
    if (project_path / ".github/workflows").exists():
        found.append("github-actions")
    if (project_path / ".gitlab-ci.yml").exists():
        found.append("gitlab-ci")
    if (project_path / "Jenkinsfile").exists():
        found.append("jenkins")
    return found


def detect_has_backend(project_path: Path) -> bool:
    backend_dirs = ["backend", "api", "server", "app"]
    for d in backend_dirs:
        if (project_path / d).is_dir():
            return True
    return False


def detect_has_frontend(project_path: Path) -> bool:
    frontend_dirs = ["frontend", "client", "ui", "src"]
    for d in frontend_dirs:
        if (project_path / d).is_dir():
            return True
    return False


def detect_config_files(project_path: Path) -> list[str]:
    important = [
        "package.json", "composer.json", "tsconfig.json", "vite.config.ts",
        "vite.config.js", "next.config.js", "next.config.ts", "tailwind.config.js",
        "tailwind.config.ts", "artisan", ".env", ".env.example", "Dockerfile",
        "docker-compose.yml", "prisma/schema.prisma", "Makefile", "pyproject.toml",
        "Cargo.toml", "go.mod", "Gemfile", "Rakefile", "webpack.config.js",
        "nuxt.config.js", "nuxt.config.ts", "nest-cli.json",
    ]
    detected = []
    for name in important:
        if (project_path / name).exists():
            detected.append(name)
    return detected
