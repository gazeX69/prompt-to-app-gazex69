"""
Capability-based skill routing engine.

Takes a scan result and returns activated skills.
Supports multi-skill activation and fallback routing.
"""

import logging
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


async def route_for_prompt(prompt: str, enabled_skills: list[str] | None = None) -> RouteResult:
    """
    Simple tag-based routing from a prompt string.
    Used when no existing project is being scanned.
    `enabled_skills` is an optional list of skill names to restrict routing to.
    """
    prompt_lower = prompt.lower()
    tags = []

    keyword_map = {
        "react": "react",
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

    for keyword, tag in keyword_map.items():
        if keyword in prompt_lower:
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
            result.fallbacks = all_skills[1:]

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
