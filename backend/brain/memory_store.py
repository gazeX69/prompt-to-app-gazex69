import json
from pathlib import Path


MEMORY_DIR = Path(__file__).resolve().parent / "memory"
MEMORY_FILES = {
    "cases": "cases.json",
    "plans": "plans.json",
    "decisions": "decisions.json",
    "failures": "failures.json",
}


def ensure_memory_files() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for filename in MEMORY_FILES.values():
        path = MEMORY_DIR / filename
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")


def _load_array(filename: str) -> list[dict]:
    ensure_memory_files()
    path = MEMORY_DIR / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def load_cases() -> list[dict]:
    return _load_array(MEMORY_FILES["cases"])


def load_plans() -> list[dict]:
    return _load_array(MEMORY_FILES["plans"])


def load_decisions() -> list[dict]:
    return _load_array(MEMORY_FILES["decisions"])


def load_failures() -> list[dict]:
    return _load_array(MEMORY_FILES["failures"])

