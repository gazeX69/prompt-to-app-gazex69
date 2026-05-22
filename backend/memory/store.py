"""
In-memory store for project generation history.

Currently uses a simple dict (process-local).
Designed to be swapped for Redis, PostgreSQL, or a vector store
without changing the interface.

Future use cases:
- Store prompt → file mappings for cache reuse.
- Feed prior repair attempts back into context.
- Support multi-agent coordination via shared memory.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ProjectRecord:
    project_id: str
    prompt: str
    files_written: list[str]
    repair_attempts: int
    success: bool
    created_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


# Global in-process store — replace with DB adapter for production
_store: dict[str, list[ProjectRecord]] = {}


def record_generation(record: ProjectRecord) -> None:
    """Append a generation record for a project."""
    _store.setdefault(record.project_id, []).append(record)


def get_history(project_id: str) -> list[ProjectRecord]:
    """Return generation history for a project, oldest first."""
    return _store.get(project_id, [])


def clear_history(project_id: str) -> None:
    """Remove all records for a project (e.g., on reset)."""
    _store.pop(project_id, None)
