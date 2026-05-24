import shutil
from pathlib import Path

from backend.agent.tools import _safe_project_path
from backend.utils.project_root import find_project_root

TEMPLATES_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = find_project_root(Path(__file__))

CANONICAL_REACT_VITE_TEMPLATE = PROJECT_ROOT / "templates" / "react-vite-ts"

TEMPLATE_ALIASES = {
    "vite-react-ts": CANONICAL_REACT_VITE_TEMPLATE,
    "react-vite-ts": CANONICAL_REACT_VITE_TEMPLATE,
}

def scaffold_template(project_id: str, template_name: str, run_id: str = None) -> None:
    src = TEMPLATE_ALIASES.get(template_name, TEMPLATES_DIR / template_name)
    dst = _safe_project_path(project_id, run_id)

    if not src.exists():
        raise ValueError(
            f"Template '{template_name}' not found. Resolved path: {src}"
        )

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)

