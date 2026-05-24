import json
import logging
from pydantic import BaseModel
from typing import List

from backend.services.ai_service import complete

logger = logging.getLogger(__name__)


class ExecutionStage(BaseModel):
    name: str
    description: str


class ExecutionPlan(BaseModel):
    goal: str
    predicted_dependencies: List[str]
    stages: List[ExecutionStage]


class PlannerEngine:
    """
    Decomposes user goals and predicts dependencies before execution.
    Currently uses deterministic templates for stability, but allows AI to extract specific dependencies.
    """
    
    @staticmethod
    async def create_plan(prompt: str, ecosystem_label: str) -> ExecutionPlan:
        # Base deterministic stages
        stages = [
            ExecutionStage(name="Scaffolding", description="Setup basic infrastructure and project files"),
            ExecutionStage(name="Generation", description="Generate feature-specific code based on prompt"),
            ExecutionStage(name="Validation", description="Verify file structure and configuration correctness")
        ]
        
        if ecosystem_label in ("React + Vite + TypeScript", "Node.js"):
            stages.append(ExecutionStage(name="Dependency Installation", description="Install required npm packages"))
            if ecosystem_label == "React + Vite + TypeScript":
                stages.append(ExecutionStage(name="Build", description="Compile TypeScript and build assets"))
                stages.append(ExecutionStage(name="Preview", description="Launch Vite dev server"))
        
        # Simple extraction prompt to predict dependencies without hallucinating architecture
        extraction_prompt = (
            f"Based on this user request for a {ecosystem_label} project:\n"
            f"\"{prompt}\"\n\n"
            f"List ONLY the 3-5 core third-party dependencies (like npm packages or pip modules) needed, "
            f"as a raw comma-separated list. No explanations."
        )
        
        predicted_deps = []
        try:
            import asyncio
            raw_deps = await asyncio.to_thread(complete, "You are a technical planner. Output only comma separated package names.", extraction_prompt)
            predicted_deps = [d.strip() for d in raw_deps.split(",") if d.strip()]
        except Exception as e:
            logger.warning(f"Failed to predict dependencies: {e}")
            predicted_deps = ["none"]
            
        return ExecutionPlan(
            goal=prompt,
            predicted_dependencies=predicted_deps,
            stages=stages
        )
