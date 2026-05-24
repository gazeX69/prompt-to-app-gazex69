import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from backend.sandbox.executor import _safe_project_path

@dataclass
class ProjectMap:
    project_id: str
    run_id: str
    ecosystem: str = "unknown"
    runtime_type: str = "unknown"
    frameworks: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    dependencies: dict[str, str] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    missing_components: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "project_id": self.project_id,
            "run_id": self.run_id,
            "ecosystem": self.ecosystem,
            "runtime_type": self.runtime_type,
            "frameworks": self.frameworks,
            "entrypoints": self.entrypoints,
            "modules": self.modules,
            "dependencies": self.dependencies,
            "risks": self.risks,
            "missing_components": self.missing_components,
        }

class ProjectMapper:
    """
    ProjectMapper is a read-only analysis module.
    It inspects the project directory and determines the ProjectMap,
    which is then used by the PlanningEngine.
    """
    def __init__(self, project_id: str, run_id: str):
        self.project_id = project_id
        self.run_id = run_id
        self.project_path = _safe_project_path(project_id, run_id)

    async def map_project(self, default_ecosystem: str = "unknown") -> ProjectMap:
        pmap = ProjectMap(project_id=self.project_id, run_id=self.run_id, ecosystem=default_ecosystem)
        
        print(f"[P7.6] repo scan root={self.project_path}")
        
        physical_entrypoints = []
        inferred_entrypoints = []

        if not self.project_path.exists():
            pmap.risks.append("Project path does not exist (new project)")

        # Detect package.json
        pkg_json_path = self.project_path / "package.json"
        if pkg_json_path.exists():
            try:
                with open(pkg_json_path, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    pmap.dependencies.update(pkg_data.get("dependencies", {}))
                    pmap.dependencies.update(pkg_data.get("devDependencies", {}))
                    
                if "react" in pmap.dependencies:
                    pmap.frameworks.append("react")
                if "vite" in pmap.dependencies:
                    pmap.frameworks.append("vite")
                    pmap.runtime_type = "spa_dev_server"
                    if pmap.ecosystem == "unknown":
                        pmap.ecosystem = "react-vite"
            except Exception as e:
                pmap.risks.append(f"Failed to parse package.json: {e}")

        # Detect PHP
        if self.project_path.exists() and list(self.project_path.glob("*.php")):
            if pmap.ecosystem == "unknown":
                pmap.ecosystem = "php-basic"
            pmap.runtime_type = "php_builtin"
            if (self.project_path / "index.php").exists():
                physical_entrypoints.append("index.php")

        # Detect Static HTML
        if self.project_path.exists() and (self.project_path / "index.html").exists() and pmap.ecosystem == "unknown":
            pmap.ecosystem = "static-html"
            pmap.runtime_type = "static"
            physical_entrypoints.append("index.html")

        # Inference based on ecosystem
        if pmap.ecosystem == "react-vite":
            pmap.runtime_type = "spa_dev_server"
            if "react" not in pmap.frameworks: pmap.frameworks.append("react")
            if "vite" not in pmap.frameworks: pmap.frameworks.append("vite")
            inferred_entrypoints = ["index.html", "src/main.tsx", "src/App.tsx", "package.json", "vite.config.ts", "tsconfig.json"]
        elif pmap.ecosystem == "php-basic":
            pmap.runtime_type = "php_builtin"
            inferred_entrypoints = ["index.php", "style.css"]
            # Also adding optional typical entrypoints to match instructions
            inferred_entrypoints.extend(["register.php", "dashboard.php", "logout.php"])
        elif "react" in pmap.frameworks:
            inferred_entrypoints = ["src/index.tsx", "src/App.tsx"]

        final_entrypoints = list(set(physical_entrypoints + inferred_entrypoints))
        pmap.entrypoints = sorted(final_entrypoints)

        print(f"[P7.6] detected ecosystem={pmap.ecosystem}")
        print(f"[P7.6] physical entrypoints={physical_entrypoints}")
        print(f"[P7.6] inferred entrypoints={inferred_entrypoints}")
        print(f"[P7.6] final entrypoints={pmap.entrypoints}")

        # Add basic modules discovery
        if self.project_path.exists():
            for root, dirs, files in os.walk(self.project_path):
                if ".git" in root or "node_modules" in root:
                    continue
                for d in dirs:
                    if d in ["components", "stores", "panels", "api", "models"]:
                        pmap.modules.append(d)

        return pmap
