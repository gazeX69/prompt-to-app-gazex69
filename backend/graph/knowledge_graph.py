import json
from pathlib import Path
from backend.agent.tools import _safe_project_path

class KnowledgeGraph:
    """Builds a rudimentary AST / file dependency graph of the project."""
    
    @staticmethod
    def get_dependencies(project_id: str, run_id: str = None) -> list:
        project_path = _safe_project_path(project_id, run_id)
        pkg_json = project_path / "package.json"
        
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                deps = list(data.get("dependencies", {}).keys())
                dev_deps = list(data.get("devDependencies", {}).keys())
                return deps + dev_deps
            except Exception:
                pass
        return []

    @staticmethod
    def get_file_tree(project_id: str, run_id: str = None) -> dict:
        project_path = _safe_project_path(project_id, run_id)
        tree = {}
        for p in project_path.rglob("*"):
            if "node_modules" in p.parts or ".git" in p.parts:
                continue
            if p.is_file():
                rel = p.relative_to(project_path)
                tree[str(rel)] = "file"
        return tree

    @staticmethod
    def build_architecture_map(project_id: str, run_id: str = None) -> dict:
        return {
            "dependencies": KnowledgeGraph.get_dependencies(project_id, run_id),
            "files": list(KnowledgeGraph.get_file_tree(project_id, run_id).keys())
        }
