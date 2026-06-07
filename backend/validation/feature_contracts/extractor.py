import json
import logging
import re
from pathlib import Path
from typing import Any

from backend.agent.tools import _safe_project_path

from .models import FeatureDescriptor, FeatureManifest

logger = logging.getLogger(__name__)

FEATURE_MANIFEST_RELATIVE_PATH = ".ai-agent/features.json"

ACTION_ALIASES: dict[str, tuple[str, str]] = {
    "add": ("create", "create"),
    "create": ("create", "create"),
    "new": ("create", "create"),
    "insert": ("create", "create"),
    "edit": ("edit", "update"),
    "update": ("update", "update"),
    "modify": ("update", "update"),
    "change": ("update", "update"),
    "delete": ("delete", "delete"),
    "remove": ("delete", "delete"),
    "clear": ("delete", "delete"),
    "persist": ("persist", "persist"),
    "save": ("persist", "persist"),
    "storage": ("persist", "persist"),
    "localstorage": ("persist", "persist"),
    "search": ("search", "search"),
    "filter": ("filter", "filter"),
    "login": ("login", "auth"),
    "auth": ("login", "auth"),
    "upload": ("upload", "file"),
    "download": ("download", "file"),
    "checkout": ("checkout", "commerce"),
}

OBJECT_ALIASES: dict[str, str] = {
    "todo": "task",
    "todos": "task",
    "todolist": "task",
    "task": "task",
    "tasks": "task",
    "item": "item",
    "items": "item",
    "stock": "stock",
    "inventory": "item",
    "entity": "entity",
    "entities": "entity",
    "product": "product",
    "products": "product",
    "cart": "cart",
    "customer": "customer",
    "customers": "customer",
    "user": "user",
    "users": "user",
    "order": "order",
    "orders": "order",
    "post": "post",
    "posts": "post",
    "page": "page",
    "pages": "page",
    "course": "course",
    "courses": "course",
    "file": "file",
    "files": "file",
}

CAPABILITY_FEATURES: dict[str, list[tuple[str, str]]] = {
    "crud": [("create_entity", "create"), ("update_entity", "update"), ("delete_entity", "delete")],
    "data_persistence": [("persist_entity", "persist")],
    "authentication": [("login_user", "auth")],
    "cart": [("add_to_cart", "commerce")],
    "checkout": [("checkout_cart", "commerce")],
    "checkout_simulation": [("checkout_cart", "commerce")],
    "product_catalog": [("create_product", "create"), ("update_product", "update")],
    "reporting": [("view_report", "reporting")],
    "search": [("search_entity", "search")],
    "filter": [("filter_entity", "filter")],
}


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    return [value]


def _normalize_token(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())


def _collect_text_from_task(task: Any) -> str:
    pieces: list[str] = []
    for key in ("title", "description"):
        value = _get_value(task, key)
        if value:
            pieces.append(str(value))
    for key in ("affected_files", "allowed_write_paths"):
        pieces.extend(str(item) for item in _as_list(_get_value(task, key)))
    for patch in _as_list(_get_value(task, "patches")):
        for key in ("operation_type", "target_file", "target_symbol", "insertion_strategy"):
            value = _get_value(patch, key)
            if value:
                pieces.append(str(value))
        pieces.extend(str(item) for item in _as_list(_get_value(patch, "expected_side_effects")))
        pieces.extend(str(item) for item in _as_list(_get_value(patch, "dependency_requirements")))
    return " ".join(pieces)


def _infer_object(text: str, fallback_domain: str | None = None) -> str:
    normalized_text = _normalize_token(text)
    for raw, canonical in OBJECT_ALIASES.items():
        if raw in normalized_text.split("_"):
            return canonical
    if fallback_domain:
        domain = _normalize_token(fallback_domain)
        return OBJECT_ALIASES.get(domain, domain)
    return "entity"


def _extract_from_text(text: str, fallback_domain: str | None = None) -> list[FeatureDescriptor]:
    lowered = text.lower()
    tokens = set(_words(text))
    detected: list[FeatureDescriptor] = []
    obj = _infer_object(text, fallback_domain)

    if "add to cart" in lowered:
        detected.append(FeatureDescriptor("add_to_cart", "commerce", 0.82, "task_description"))
    if "adjust stock" in lowered or "stock adjustment" in lowered:
        detected.append(FeatureDescriptor("adjust_stock", "update", 0.82, "task_description"))

    for alias, (action, category) in ACTION_ALIASES.items():
        if alias not in tokens and alias not in lowered:
            continue
        feature_id = f"{action}_{obj}"
        if action in {"login", "upload", "download"} and obj == "entity":
            feature_id = f"{action}_user" if action == "login" else f"{action}_file"
        detected.append(FeatureDescriptor(feature_id, category, 0.74, "task_description"))

    return detected


def _add_feature(
    features: dict[str, FeatureDescriptor],
    feature_id: str,
    category: str,
    confidence: float,
    source: str,
) -> None:
    normalized_id = _normalize_token(feature_id)
    if not normalized_id:
        return
    existing = features.get(normalized_id)
    descriptor = FeatureDescriptor(normalized_id, category or "unknown", confidence, source)
    if existing is None or descriptor.confidence > existing.confidence:
        features[normalized_id] = descriptor


class FeatureExtractor:
    def extract_features(
        self,
        *,
        project_id: str,
        run_id: str,
        prompt: str,
        generation_signature: Any | None = None,
        task_graph: Any | None = None,
        project_state: dict[str, Any] | None = None,
        implementation_plan: Any | None = None,
        planner_output: Any | None = None,
    ) -> FeatureManifest:
        project_state = project_state or {}
        app_type = _get_value(generation_signature, "app_type") or project_state.get("project_type")
        domain = _get_value(generation_signature, "domain") or project_state.get("domain")
        features: dict[str, FeatureDescriptor] = {}

        for raw in _as_list(project_state.get("features")):
            if isinstance(raw, dict):
                _add_feature(
                    features,
                    str(raw.get("id") or raw.get("feature") or raw.get("name") or "unknown_feature"),
                    str(raw.get("category") or "project_state"),
                    float(raw.get("confidence") or 0.88),
                    "project_state",
                )
            else:
                _add_feature(features, str(raw), "project_state", 0.88, "project_state")

        for capability in _as_list(_get_value(generation_signature, "required_capabilities")):
            key = _normalize_token(str(capability))
            for feature_id, category in CAPABILITY_FEATURES.get(key, []):
                _add_feature(features, feature_id, category, 0.72, "generation_signature")

        for keyword in _as_list(_get_value(generation_signature, "feature_keywords")):
            text = str(keyword)
            key = _normalize_token(text)
            if key in CAPABILITY_FEATURES:
                for feature_id, category in CAPABILITY_FEATURES[key]:
                    _add_feature(features, feature_id, category, 0.70, "generation_signature")
            else:
                extracted = _extract_from_text(text, domain)
                if extracted:
                    for feature in extracted:
                        _add_feature(features, feature.id, feature.category, 0.68, "generation_signature")
                else:
                    _add_feature(features, key, "keyword", 0.55, "generation_signature")

        for source_name, source in (
            ("implementation_plan", implementation_plan),
            ("planner_output", planner_output),
        ):
            for item in _as_list(source):
                for feature in _extract_from_text(str(item), domain):
                    _add_feature(features, feature.id, feature.category, 0.66, source_name)

        tasks = _get_value(task_graph, "tasks", {}) if task_graph is not None else {}
        task_values = tasks.values() if isinstance(tasks, dict) else _as_list(tasks)
        for task in task_values:
            text = _collect_text_from_task(task)
            for feature in _extract_from_text(text, domain):
                _add_feature(features, feature.id, feature.category, feature.confidence, "task_graph")

        for feature in _extract_from_text(prompt, domain):
            _add_feature(features, feature.id, feature.category, 0.60, "prompt")

        if not features:
            _add_feature(features, "unknown_feature", "unknown", 0.0, "fallback")

        manifest = FeatureManifest(
            project_id=project_id,
            run_id=run_id,
            app_type=app_type,
            domain=domain,
            features=sorted(features.values(), key=lambda feature: feature.id),
        )
        logger.info("[FeatureExtraction] features: %s", [feature.id for feature in manifest.features])
        return manifest


def extract_features(**kwargs: Any) -> FeatureManifest:
    return FeatureExtractor().extract_features(**kwargs)


def feature_manifest_path(project_id: str) -> Path:
    return _safe_project_path(project_id) / FEATURE_MANIFEST_RELATIVE_PATH


def save_feature_manifest(project_id: str, manifest: FeatureManifest) -> Path:
    path = feature_manifest_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_feature_manifest(project_id: str) -> FeatureManifest | None:
    path = feature_manifest_path(project_id)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    features = [
        FeatureDescriptor(
            id=str(item.get("id") or "unknown_feature"),
            category=str(item.get("category") or "unknown"),
            confidence=float(item.get("confidence") or 0.0),
            source=str(item.get("source") or "unknown"),
        )
        for item in raw.get("features", [])
        if isinstance(item, dict)
    ]
    return FeatureManifest(
        project_id=str(raw.get("project_id") or project_id),
        run_id=str(raw.get("run_id") or ""),
        app_type=raw.get("app_type"),
        domain=raw.get("domain"),
        features=features,
        source=str(raw.get("source") or "feature_extraction"),
    )
