"""
Filesystem utilities for the AI agent workspace.

Safety guarantees:
- All writes are confined to WORKSPACE_ROOT.
- Path traversal attempts raise ValueError.
- Filenames are validated before write.
- File content size is capped at FILE_SIZE_LIMIT_BYTES.
"""

import re
from pathlib import Path

WORKSPACE_ROOT = Path("workspaces")
FILE_SIZE_LIMIT_BYTES = 512 * 1024  # 512 KB per file

# Characters not allowed in path segments
_UNSAFE_SEGMENT_RE = re.compile(r"[<>:\"\\|?*\x00-\x1f]")


def _safe_project_path(project_id: str) -> Path:
    """Resolve project path and ensure it stays inside WORKSPACE_ROOT."""
    if not project_id or "/" in project_id or "\\" in project_id or ".." in project_id:
        raise ValueError(f"Invalid project_id: {project_id!r}")
    return WORKSPACE_ROOT / project_id


def _validate_relative_path(rel_path: str) -> Path:
    """
    Convert a relative path string into a safe Path object.
    Raises ValueError if the path looks malicious.
    """
    p = Path(rel_path)

    if p.is_absolute():
        raise ValueError(f"Absolute paths are not allowed: {rel_path!r}")

    for part in p.parts:
        if part == "..":
            raise ValueError(f"Path traversal detected in: {rel_path!r}")
        if _UNSAFE_SEGMENT_RE.search(part):
            raise ValueError(f"Unsafe characters in path segment: {part!r}")

    return p


def create_project(project_id: str) -> Path:
    """Create the project workspace directory if it does not exist."""
    project_path = _safe_project_path(project_id)
    project_path.mkdir(parents=True, exist_ok=True)
    return project_path


def write_file(project_id: str, relative_path: str, content: str) -> str:
    """
    Write a file into the project workspace.

    Args:
        project_id:     Name of the project folder inside WORKSPACE_ROOT.
        relative_path:  File path relative to the project root (e.g. "src/App.jsx").
        content:        Text content to write.

    Returns:
        The absolute string path of the written file.

    Raises:
        ValueError: On path traversal, invalid names, or oversized content.
    """
    if len(content.encode("utf-8")) > FILE_SIZE_LIMIT_BYTES:
        raise ValueError(
            f"File content exceeds size limit ({FILE_SIZE_LIMIT_BYTES} bytes): {relative_path!r}"
        )

    safe_rel = _validate_relative_path(relative_path)
    project_path = create_project(project_id)
    file_path = project_path / safe_rel

    # Resolve and re-check that the final path is still inside the workspace
    resolved = file_path.resolve()
    workspace_resolved = WORKSPACE_ROOT.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise ValueError(f"Path escapes workspace: {relative_path!r}")

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return str(file_path)

def append_file(project_id: str, relative_path: str, content: str) -> str:
    """Append content to a file in the project workspace."""
    safe_rel = _validate_relative_path(relative_path)
    project_path = create_project(project_id)
    file_path = project_path / safe_rel

    resolved = file_path.resolve()
    workspace_resolved = WORKSPACE_ROOT.resolve()
    if not str(resolved).startswith(str(workspace_resolved)):
        raise ValueError(f"Path escapes workspace: {relative_path!r}")

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(content + "\n")

    return str(file_path)


def read_file(project_id: str, relative_path: str) -> str:
    """Read a file from the project workspace."""
    safe_rel = _validate_relative_path(relative_path)
    project_path = _safe_project_path(project_id)
    file_path = project_path / safe_rel

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    return file_path.read_text(encoding="utf-8")


def list_project_files(project_id: str) -> list[str]:
    """Return all file paths inside the project workspace, relative to it."""
    project_path = _safe_project_path(project_id)
    if not project_path.exists():
        return []
    return [
        str(p.relative_to(project_path))
        for p in project_path.rglob("*")
        if p.is_file()
    ]
