from dataclasses import dataclass
from enum import Enum


class ArtifactCategory(str, Enum):
    TYPE = "TYPE"
    STORE = "STORE"
    COMPONENT = "COMPONENT"
    PAGE = "PAGE"
    APP_ENTRY = "APP_ENTRY"
    OTHER = "OTHER"


@dataclass(frozen=True)
class ArtifactDescriptor:
    name: str
    artifact_category: ArtifactCategory = ArtifactCategory.OTHER


def classify_artifact(name: str, declaration_kind: str, file_path: str) -> ArtifactCategory:
    normalized_path = (file_path or "").replace("\\", "/").lower()
    if normalized_path.endswith("/app.tsx") or normalized_path.endswith("/app.jsx") or normalized_path in {"app.tsx", "app.jsx"}:
        if name == "App":
            return ArtifactCategory.APP_ENTRY

    if declaration_kind in {"interface", "type", "enum"}:
        return ArtifactCategory.TYPE

    if name.startswith("use") and len(name) > 3 and name[3].isupper():
        return ArtifactCategory.STORE

    if name.endswith("Page"):
        return ArtifactCategory.PAGE

    if declaration_kind in {"function", "class", "const", "default_function"} and name[:1].isupper():
        return ArtifactCategory.COMPONENT

    return ArtifactCategory.OTHER
