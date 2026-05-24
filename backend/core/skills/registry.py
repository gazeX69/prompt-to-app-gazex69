import logging
from typing import Optional

from backend.core.skills.interfaces import BaseSkill, SkillMetadata

logger = logging.getLogger(__name__)

_skills: dict[str, BaseSkill] = {}
_skills_by_capability: dict[str, list[BaseSkill]] = {}
_skills_by_language: dict[str, list[BaseSkill]] = {}
_skills_by_type: dict[str, list[BaseSkill]] = {}


def register_skill(skill: BaseSkill) -> None:
    meta = skill.metadata
    _skills[meta.name] = skill

    for cap in meta.capabilities:
        _skills_by_capability.setdefault(cap, []).append(skill)

    _skills_by_language.setdefault(meta.language, []).append(skill)
    _skills_by_type.setdefault(meta.type, []).append(skill)

    logger.info("Skill registered: %s (type=%s, lang=%s, caps=%s)", meta.name, meta.type, meta.language, meta.capabilities)


def unregister_skill(name: str) -> None:
    skill = _skills.pop(name, None)
    if skill is None:
        return
    meta = skill.metadata
    for cap in meta.capabilities:
        if cap in _skills_by_capability:
            _skills_by_capability[cap] = [s for s in _skills_by_capability[cap] if s.metadata.name != name]
    if meta.language in _skills_by_language:
        _skills_by_language[meta.language] = [s for s in _skills_by_language[meta.language] if s.metadata.name != name]
    if meta.type in _skills_by_type:
        _skills_by_type[meta.type] = [s for s in _skills_by_type[meta.type] if s.metadata.name != name]
    logger.info("Skill unregistered: %s", name)


def get_skill(name: str) -> Optional[BaseSkill]:
    return _skills.get(name)


def get_all_skills() -> list[BaseSkill]:
    return list(_skills.values())


def get_skills_by_capability(capability: str) -> list[BaseSkill]:
    return _skills_by_capability.get(capability, [])


def get_skills_by_language(language: str) -> list[BaseSkill]:
    return _skills_by_language.get(language, [])


def get_skills_by_type(type_name: str) -> list[BaseSkill]:
    return _skills_by_type.get(type_name, [])


def get_skills_metadata() -> list[SkillMetadata]:
    return [s.metadata for s in _skills.values()]


async def find_skills(context: dict, enabled_only: list[str] | None = None) -> list[BaseSkill]:
    matched: list[BaseSkill] = []
    for skill in _skills.values():
        if enabled_only is not None and skill.metadata.name not in enabled_only:
            logger.debug("Skill %s filtered out (disabled)", skill.metadata.name)
            continue
        try:
            if await skill.can_handle(context):
                matched.append(skill)
        except Exception as e:
            logger.warning("Skill %s.can_handle() raised: %s", skill.metadata.name, e)
    return matched
