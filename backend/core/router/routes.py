"""
Capability-based skill routing engine.

Takes a scan result and returns activated skills.
Supports multi-skill activation and fallback routing.
"""

import logging
import re
from typing import Optional

from backend.core.scanner.engine import ProjectScanResult
from backend.core.skills.interfaces import BaseSkill
from backend.core.skills.registry import get_all_skills, find_skills, get_skills_by_capability

logger = logging.getLogger(__name__)


class ActivatedSkill:
    def __init__(self, skill: BaseSkill, reason: str):
        self.skill = skill
        self.reason = reason

    @property
    def metadata(self):
        return self.skill.metadata


class RouteResult:
    def __init__(self, primary: Optional[BaseSkill] = None, activated: list[ActivatedSkill] = None):
        self.primary = primary
        self.activated = activated or []
        self.fallbacks: list[BaseSkill] = []

    @property
    def primary_name(self) -> str:
        return self.primary.metadata.name if self.primary else "none"

    @property
    def activated_names(self) -> list[str]:
        return [a.metadata.name for a in self.activated]

    def to_dict(self) -> dict:
        return {
            "primary": self.primary_name,
            "activated": self.activated_names,
            "fallback_count": len(self.fallbacks),
        }


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z0-9_]){re.escape(word)}(?![a-z0-9_])", text) is not None


def _has_phrase_or_word(text: str, keyword: str) -> bool:
    keyword = keyword.lower().strip()
    if " " in keyword or "/" in keyword or "." in keyword or "-" in keyword:
        return keyword in text
    return _has_word(text, keyword)


def _skill_by_name(name: str, enabled_skills: list[str] | None = None) -> Optional[BaseSkill]:
    if enabled_skills is not None and name not in enabled_skills:
        return None

    for skill in get_all_skills():
        if skill.metadata.name == name:
            return skill

    return None


def _route_to_skill(
    name: str,
    reason: str,
    enabled_skills: list[str] | None = None,
) -> RouteResult | None:
    skill = _skill_by_name(name, enabled_skills)
    if not skill:
        return None

    available = get_all_skills()
    if enabled_skills is not None:
        available = [s for s in available if s.metadata.name in enabled_skills]

    result = RouteResult(primary=skill)
    result.activated.append(ActivatedSkill(skill, reason))
    result.fallbacks = [s for s in available if s.metadata.name != name]
    return result


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _has_frontend_target(text: str) -> bool:
    frontend_keywords = [
        "target ecosystem: react-vite",
        "react-vite",
        "react + vite",
        "react/vite",
        "react",
        "vite",
        "frontend",
        "client-side",
        "client side",
        "ui",
        "browser ui",
        "previewable",
        "root route",
        'route "/"',
    ]
    return _has_any(text, frontend_keywords)


def _is_explicit_backend_request(text: str) -> bool:
    # These phrases mean backend/server words are restrictions, not requests.
    backend_negation_phrases = [
        "do not create backend",
        "do not create a backend",
        "do not create backend/api",
        "do not create a backend/api",
        "do not create server-side",
        "do not create server side",
        "without backend",
        "no backend",
        "tanpa backend",
        "unless backend",
        "unless a backend",
        "unless explicitly requested",
        "unless explicitly required",
        "kecuali diminta",
        "kecuali diminta eksplisit",
    ]

    if _has_frontend_target(text):
        return False

    if _has_any(text, backend_negation_phrases):
        return False

    explicit_backend_keywords = [
        "rest api",
        "backend api",
        "api",
        "backend",
        "express",
        "node server",
        "server node",
        "server.js",
        "api server",
        "endpoint",
        "database",
        "sql",
        "mysql",
        "postgres",
        "postgresql",
        "sqlite",
        "mongodb",
    ]

    return any(_has_phrase_or_word(text, keyword) for keyword in explicit_backend_keywords)


def _should_force_node_backend(prompt: str) -> bool:
    text = prompt.lower()

    if _has_frontend_target(text):
        return False

    return _is_explicit_backend_request(text)


def _should_force_react_vite(prompt: str) -> bool:
    text = prompt.lower()

    if _has_frontend_target(text):
        return True

    if _is_explicit_backend_request(text):
        return False

    previewable_mvp_keywords = [
        "hello world",
        "counter",
        "todo",
        "todo list",
        "crud",
        "crud sederhana",
        "inventory",
        "inventory sederhana",
        "dashboard sederhana",
        "local storage",
        "localstorage",
        "mock data",
        "mvp",
        "recommended mvp",
        "use this confirmed mvp scope",
    ]

    return _has_any(text, previewable_mvp_keywords)


async def route_for_scan(scan: ProjectScanResult) -> RouteResult:
    """
    Given a ProjectScanResult, determine which skills to activate.
    """
    result = RouteResult()
    context = _scan_to_context(scan)

    matched = await find_skills(context)
    if matched:
        result.primary = matched[0]
        for s in matched:
            result.activated.append(ActivatedSkill(s, f"matched framework={scan.framework}"))
    else:
        logger.info("No direct skill match for framework=%s, trying capability routing", scan.framework)
        for cap in scan.capabilities:
            for skill in get_skills_by_capability(cap):
                if not any(a.metadata.name == skill.metadata.name for a in result.activated):
                    result.activated.append(ActivatedSkill(skill, f"capability={cap}"))

        if not result.activated:
            logger.info("No skill matched by capability either, using fallback")
            all_skills = get_all_skills()
            if all_skills:
                result.primary = all_skills[0]
                result.activated.append(ActivatedSkill(all_skills[0], "fallback: first available"))
                result.fallbacks = all_skills[1:]

    if result.activated and not result.primary:
        result.primary = result.activated[0].skill

    return result

keyword_map = {
    "react": "react",
    "vite": "react",
    "vue": "vue",
    "next": "nextjs",
    "laravel": "laravel",
    "php": "php",
    "php-basic": "php",
    "node": "node",
    "express": "express",
    "api": "api",
    "frontend": "frontend",
    "backend": "backend",
    "fullstack": "fullstack",
    "tailwind": "tailwind",
}


async def route_for_prompt(prompt: str, enabled_skills: list[str] | None = None) -> RouteResult:
    """
    Simple tag-based routing from a prompt string.
    Used when no existing project is being scanned.
    `enabled_skills` is an optional list of skill names to restrict routing to.
    """
    prompt_lower = prompt.lower()

    if _should_force_node_backend(prompt):
        forced = _route_to_skill(
            "node-backend",
            "forced: explicit backend/API/database request",
            enabled_skills,
        )
        if forced:
            return forced

    if _should_force_react_vite(prompt):
        forced = _route_to_skill(
            "react-vite",
            "forced: previewable frontend MVP/simple app",
            enabled_skills,
        )
        if forced:
            return forced

    tags = []

    for keyword, tag in keyword_map.items():
        if _has_phrase_or_word(prompt_lower, keyword):
            tags.append(tag)

    context = {"framework": "", "tags": tags}
    result = RouteResult()
    matched = await find_skills(context, enabled_only=enabled_skills)

    if matched:
        result.primary = matched[0]
        for s in matched:
            result.activated.append(ActivatedSkill(s, f"prompt-match: tags={tags}"))
    else:
        all_skills = get_all_skills()
        if enabled_skills is not None:
            all_skills = [s for s in all_skills if s.metadata.name in enabled_skills]
        if all_skills:
            result.primary = all_skills[0]
            result.activated.append(ActivatedSkill(all_skills[0], "fallback: first available"))
            result.fallbacks = [s for s in all_skills if s.metadata.name != result.primary.metadata.name]

    return result


def _scan_to_context(scan: ProjectScanResult) -> dict:
    tags = []
    if scan.framework:
        tags.append(scan.framework)
    if scan.language:
        tags.append(scan.language)
    if scan.uses_tailwind:
        tags.append("tailwind")
    if scan.uses_prisma:
        tags.append("prisma")
    return {
        "framework": scan.framework or "",
        "language": scan.language or "",
        "tags": tags,
        "capabilities": scan.capabilities,
    }
