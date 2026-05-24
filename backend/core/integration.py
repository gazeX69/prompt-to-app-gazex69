"""
Integration facade connecting the new modular systems with the existing orchestrator.

This module provides clean entry points for:
  - Scanning a project
  - Activating skills based on scan results
  - Building a patch plan for existing project modification
  - Classifying runtime errors

It does NOT modify the existing orchestrator. It provides a superset of capabilities
that can be used alongside or instead of the hardcoded flow.
"""

import logging
from pathlib import Path
from typing import Optional

from backend.core.scanner.engine import scan_project, ProjectScanResult
from backend.core.scanner.detectors import detect_package_manager, detect_framework, detect_language
from backend.core.router.routes import route_for_scan, RouteResult
from backend.core.skills.registry import register_skill, get_skill, get_skills_metadata, find_skills
from backend.core.skills.interfaces import BaseSkill, SkillMetadata
from backend.core.patcher.patch import build_patch_plan, apply_patch_plan, PatchPlan
from backend.core.observer.errors import (
    analyze_build_output,
    analyze_dev_output,
    Diagnostic,
    ErrorCategory,
)

logger = logging.getLogger(__name__)


async def prepare_project_context(project_path: str | Path) -> dict:
    path = Path(project_path).resolve()
    scan = scan_project(str(path))
    route = await route_for_scan(scan)
    return {
        "path": str(path),
        "scan": scan.to_dict(),
        "route": route.to_dict(),
        "primary_skill": route.primary_name,
        "activated_skills": route.activated_names,
    }


async def generate_with_skills(prompt: str, project_id: str, project_path: str | Path) -> dict:
    scan = scan_project(project_path)
    route = await route_for_scan(scan)

    result = {
        "project_id": project_id,
        "prompt": prompt,
        "scan": scan.to_dict(),
        "route": route.to_dict(),
        "activated_skills": [],
        "files_written": [],
        "success": False,
    }

    for activated in route.activated:
        skill = activated.skill
        logger.info("Activating skill: %s (reason: %s)", skill.metadata.name, activated.reason)
        try:
            skill_result = await skill.execute({
                "prompt": prompt,
                "project_id": project_id,
                "project_path": str(project_path),
                "scan": scan.to_dict(),
            })
            result["activated_skills"].append({
                "name": skill.metadata.name,
                "status": skill_result.get("status", "executed"),
            })
        except Exception as e:
            logger.error("Skill %s execution failed: %s", skill.metadata.name, e)
            result["activated_skills"].append({
                "name": skill.metadata.name,
                "status": f"error: {e}",
            })

    result["success"] = True
    return result
