from pathlib import Path

def find_project_root(start: Path) -> Path:
    current = start.resolve()

    while current != current.parent:
        if (current / "templates").exists() and (current / "backend").exists():
            return current

        current = current.parent

    raise RuntimeError("Unable to locate project root.")