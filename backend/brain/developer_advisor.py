import os
import json
import logging
from pathlib import Path
from backend.services.ai_service import complete
from backend.brain.schemas import DevelopmentAdvisory, AdvisorySuggestion
from backend.sandbox.executor import _safe_project_path

logger = logging.getLogger(__name__)

class DeveloperAdvisor:
    @staticmethod
    def generate_suggestions(project_id: str, run_id: str, prompt: str, is_success: bool = True) -> DevelopmentAdvisory:
        # Resolve target project path
        base_path = _safe_project_path(project_id, run_id)
        
        # Gather directory listing and some file content for context
        file_tree_context = ""
        sample_code_context = ""
        try:
            if base_path.exists():
                for root, dirs, files in os.walk(base_path):
                    # Skip dependency and build dirs
                    dirs[:] = [d for d in dirs if d not in ("node_modules", "dist", ".git", ".orchestration", "vendor")]
                    rel_dir = os.path.relpath(root, base_path)
                    if rel_dir == ".":
                        rel_dir = ""
                    for f in files:
                        filepath = os.path.join(rel_dir, f).replace("\\", "/")
                        file_tree_context += f"- {filepath}\n"
                        # Sample App.tsx or main entrypoints for coding style/imports
                        if f in ("App.tsx", "index.css", "main.tsx", "App.jsx") or (f.endswith(".php") and f != "index.php"):
                            try:
                                full_p = Path(root) / f
                                content = full_p.read_text(encoding="utf-8")
                                sample_code_context += f"\n--- FILE: {filepath} ---\n{content[:1500]}\n"
                            except Exception:
                                pass
        except Exception as e:
            logger.warning(f"Error scanning files for advisor context: {e}")
            
        system_prompt = (
            "You are a professional software architect and tech lead. You analyze developer prompts and generated codebases to provide high-quality next-step advisory. "
            "You MUST respond ONLY with a valid JSON object matching the DevelopmentAdvisory schema. Do not enclose in markdown blocks other than json format or include additional text.\n"
            "JSON Format:\n"
            "{\n"
            '  "project_id": "string",\n'
            '  "run_id": "string",\n'
            '  "current_status": "succeeded | failed",\n'
            '  "analysis": "1-2 sentence overview of the current status and design quality.",\n'
            '  "suggestions": [\n'
            '    {\n'
            '      "title": "Short title of suggestion",\n'
            '      "description": "Clear actionable step of what should be done next",\n'
            '      "difficulty": "low | medium | high",\n'
            '      "impact": "low | medium | high",\n'
            '      "suggested_files": ["list of relative file paths to edit/create"],\n'
            '      "command": null\n'
            "    }\n"
            "  ]\n"
            "}"
        )
        
        user_prompt = (
            f"Original Request Prompt: '{prompt}'\n"
            f"Ecosystem files generated:\n{file_tree_context}\n"
            f"Sample file contents:\n{sample_code_context}\n"
            f"Generation Success: {is_success}\n"
            f"Please generate exactly 3 logical, professional next steps to expand, optimize, or secure this application."
        )
        
        try:
            raw_response = complete(system_prompt, user_prompt, max_tokens=1000, temperature=0.3)
            # Parse JSON
            import re
            json_match = re.search(r'\{.*\}', raw_response, flags=re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                # Ensure project_id and run_id match the request
                data["project_id"] = project_id
                data["run_id"] = run_id
                data["current_status"] = "succeeded" if is_success else "failed"
                
                # Validate and parse suggestions
                suggestions = []
                for s in data.get("suggestions", []):
                    suggestions.append(AdvisorySuggestion(
                        title=s.get("title", "Next Step"),
                        description=s.get("description", ""),
                        difficulty=s.get("difficulty", "medium"),
                        impact=s.get("impact", "medium"),
                        suggested_files=s.get("suggested_files", []),
                        command=s.get("command")
                    ))
                return DevelopmentAdvisory(
                    project_id=project_id,
                    run_id=run_id,
                    current_status=data["current_status"],
                    analysis=data.get("analysis", "Project analyzed successfully."),
                    suggestions=suggestions
                )
        except Exception as e:
            logger.exception(f"Failed to generate advisor recommendations: {e}")
            
        # Fallback advisory if AI fails or throws error
        fallback_suggestions = [
            AdvisorySuggestion(
                title="Add Test Suites",
                description="Write unit tests for UI components to ensure layout stability.",
                difficulty="medium",
                impact="high",
                suggested_files=["src/__tests__/App.test.tsx"]
            ),
            AdvisorySuggestion(
                title="Add State Persistence",
                description="Connect component states to localStorage or IndexedDB.",
                difficulty="low",
                impact="medium",
                suggested_files=["src/App.tsx"]
            ),
            AdvisorySuggestion(
                title="Polish UI Styling & Responsiveness",
                description="Enhance grid layouts and flex alignment for responsive mobile viewing.",
                difficulty="low",
                impact="medium",
                suggested_files=["src/App.tsx", "src/index.css"]
            )
        ]
        return DevelopmentAdvisory(
            project_id=project_id,
            run_id=run_id,
            current_status="succeeded" if is_success else "failed",
            analysis="Codebase generated. Ready for next architectural extension.",
            suggestions=fallback_suggestions
        )
