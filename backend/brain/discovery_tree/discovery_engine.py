import logging
from typing import Any

from backend.brain.discovery_tree.discovery_registry import load_node, select_root_node
from backend.brain.discovery_tree.discovery_session import create_session, load_session, save_session
from backend.brain.discovery_tree.node_schema import DiscoveryNode, DiscoverySessionState, DiscoveryTurn

logger = logging.getLogger(__name__)


class DiscoveryEngineError(RuntimeError):
    pass


def _normalize_answer(node: DiscoveryNode, answer: str) -> Any:
    raw = (answer or "").strip()
    lowered = raw.lower()
    aliases = {str(key).lower(): value for key, value in (node.answer_aliases or {}).items()}
    if lowered in aliases:
        return aliases[lowered]
    if node.answer_type == "boolean":
        if lowered in {"ya", "iya", "yes", "y", "true", "perlu"}:
            return True
        if lowered in {"tidak", "no", "n", "false", "tidak perlu"}:
            return False
    return raw


def _next_node_id(node: DiscoveryNode, normalized_answer: Any) -> str | None:
    answer_key = str(normalized_answer).lower()
    if answer_key in node.transitions:
        return node.transitions[answer_key]
    if node.default_next:
        return node.default_next
    if len(node.children) == 1:
        return node.children[0]
    return None


def build_project_state_draft(session: DiscoverySessionState) -> dict[str, Any]:
    root = load_node(session.root_node)
    draft: dict[str, Any] = {}
    if root.project_type:
        draft["project_type"] = root.project_type
    draft.update(session.answers)
    return draft


def _turn_from_session(session: DiscoverySessionState) -> DiscoveryTurn:
    question = None
    field = None
    if session.current_node and not session.complete:
        node = load_node(session.current_node)
        question = node.question
        field = node.field
    return DiscoveryTurn(
        session_id=session.session_id,
        current_node=session.current_node,
        question=question,
        field=field,
        answers=session.answers,
        draft_state=session.draft_state,
        complete=session.complete,
    )


def should_start_discovery(prompt: str) -> bool:
    return select_root_node(prompt) is not None


def start_discovery(prompt: str, project_id: str | None = None) -> DiscoveryTurn:
    root_node = select_root_node(prompt)
    if not root_node:
        raise DiscoveryEngineError("No discovery root node matches this prompt.")
    session = create_session(root_node, project_id)
    root = load_node(root_node)
    session.draft_state = build_project_state_draft(session)
    save_session(session, project_id)
    logger.info("[Discovery] Draft state updated")
    return DiscoveryTurn(
        session_id=session.session_id,
        current_node=root.id,
        question=root.question,
        field=root.field,
        answers=session.answers,
        draft_state=session.draft_state,
        complete=False,
    )


def answer_discovery(session_id: str, answer: str, project_id: str | None = None) -> DiscoveryTurn:
    session = load_session(session_id, project_id)
    if session.complete or not session.current_node:
        return _turn_from_session(session)

    node = load_node(session.current_node)
    normalized = _normalize_answer(node, answer)
    session.answers[node.field] = normalized
    logger.info("[Discovery] Answer: %s=%s", node.field, normalized)

    next_node = _next_node_id(node, normalized)
    if next_node:
        logger.info("[Discovery] Transition: %s -> %s", node.id, next_node)
        session.current_node = next_node
        next_loaded = load_node(next_node)
        if next_loaded.terminal and not next_loaded.question:
            session.complete = True
            session.current_node = None
    else:
        session.complete = True
        session.current_node = None

    session.draft_state = build_project_state_draft(session)
    logger.info("[Discovery] Draft state updated")
    if session.complete and project_id:
        try:
            from backend.memory.project_memory import ProjectMemory

            ProjectMemory.update_from_discovery_draft(
                project_id,
                session.draft_state,
                session_id=session.session_id,
            )
        except Exception:
            logger.exception("[Discovery] Failed to sync draft state into Project State")
    save_session(session, project_id)
    return _turn_from_session(session)


def restore_discovery(session_id: str, project_id: str | None = None) -> DiscoveryTurn:
    return _turn_from_session(load_session(session_id, project_id))
