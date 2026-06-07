import json
import logging
from pathlib import Path

from backend.brain.discovery_tree.node_schema import DiscoveryNode
from backend.brain.prompt_cleaning import clean_user_intent_prompt

logger = logging.getLogger(__name__)

DISCOVERY_NODES_DIR = Path(__file__).resolve().parent.parent / "discovery_nodes"
_NODE_CACHE: dict[str, DiscoveryNode] = {}


class DiscoveryRegistryError(RuntimeError):
    pass


def _safe_node_id(node_id: str) -> str:
    safe = (node_id or "").strip()
    if not safe or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for char in safe):
        raise DiscoveryRegistryError(f"Invalid discovery node id: {node_id!r}")
    return safe


def load_node(node_id: str) -> DiscoveryNode:
    safe_id = _safe_node_id(node_id)
    if safe_id in _NODE_CACHE:
        node = _NODE_CACHE[safe_id]
        logger.info("[Discovery] Loaded node: %s", node.id)
        return node

    path = DISCOVERY_NODES_DIR / f"{safe_id}.json"
    if not path.exists():
        raise DiscoveryRegistryError(f"Discovery node not found: {safe_id}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiscoveryRegistryError(f"Invalid discovery node JSON: {path.name}") from exc

    node = DiscoveryNode(**raw)
    _NODE_CACHE[safe_id] = node
    logger.info("[Discovery] Loaded node: %s", node.id)
    return node


def clear_node_cache() -> None:
    _NODE_CACHE.clear()


def select_root_node(prompt: str) -> str | None:
    text = clean_user_intent_prompt(prompt).lower()
    if "crud" in text:
        return "crud_root"
    if any(term in text for term in ["marketplace", "toko online", "online shop", "ecommerce", "e-commerce"]):
        return "marketplace_root"
    return None
