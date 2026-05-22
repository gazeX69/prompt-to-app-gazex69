import shutil
from pathlib import Path
from backend.agent.tools import _safe_project_path

TEMPLATES_DIR = Path(__file__).parent.resolve()

def scaffold_template(project_id: str, template_name: str) -> None:
    """
    Copy a predefined template to the project workspace.
    This guarantees a deterministic, bootable starting point.
    """
    src = TEMPLATES_DIR / template_name
    dst = _safe_project_path(project_id)
    
    if not src.exists():
        raise ValueError(f"Template '{template_name}' not found.")
    
    # Create the workspace directory if it doesn't exist
    dst.mkdir(parents=True, exist_ok=True)
    
    # Copy all template files to the workspace
    shutil.copytree(src, dst, dirs_exist_ok=True)
