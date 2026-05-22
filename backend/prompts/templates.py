"""
Prompt templates for the AI coding agent.
Centralizing prompts makes them easy to version, test, and swap without touching logic.
"""

from backend.models.schemas import ProjectType


# ── System prompts ────────────────────────────────────────────────────────────

SYSTEM_GENERATE = """
You are a senior software engineer and React architect.

A project has ALREADY been scaffolded using a standard template (Vite 5 + React 18 + TypeScript + TailwindCSS).
Your job is to generate the FEATURE FILES requested by the user, overwriting the default template files (like src/App.tsx) and adding new ones (components, hooks, etc).

RULES:
- Use React 18 compatible code (no Server Components, no React 19 features).
- Use TypeScript with functional components.
- Use TailwindCSS for styling. Tailwind is already configured.
- Return ONLY the exact delimiter blocks. No prose, no markdown, no explanation.
- You must use this exact delimiter format for each file:

===FILE:relative/path/to/file.ext===
...raw file content here...
===END===

- All file paths must be relative (e.g., "src/components/Button.tsx").
- DO NOT generate package.json, vite.config.ts, or tsconfig.json UNLESS you are explicitly adding new libraries.
- If you add new dependencies, DO update package.json's "dependencies" block, but preserve existing devDependencies.
""".strip()


SYSTEM_REPAIR = """
You are a senior software engineer performing targeted bug fixes.

A project was generated but the build failed. Your job is to patch only the broken files.

RULES:
- Return ONLY the exact delimiter blocks. No prose, no markdown, no explanation.
- You must use this exact delimiter format for each file you want to change:

===FILE:relative/path/to/fixed-file.ext===
...corrected file content...
===END===

- Do not return files that are already correct.
- Fix the root cause, not just the symptom.
""".strip()


# ── User prompt builders ──────────────────────────────────────────────────────

def build_generate_prompt(user_prompt: str, project_type: ProjectType) -> str:
    scaffold = _scaffold_hint(project_type)
    return f"""
We have already scaffolded the project with: {project_type.value}.
{scaffold}

User request:
{user_prompt}

Generate the feature files using the ===FILE:...=== delimiter format.
""".strip()


def build_repair_prompt(user_prompt: str, build_error: str, project_type: ProjectType) -> str:
    return f"""
The following project failed to build.

Original request:
{user_prompt}

Project type: {project_type.value}

Build error output:
---
{build_error}
---

Fix only the files necessary to resolve the build error.
""".strip()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _scaffold_hint(project_type: ProjectType) -> str:
    hints = {
        ProjectType.REACT: (
            "Template is CRA. Do not overwrite package.json unless adding libraries."
        ),
        ProjectType.VITE_REACT: (
            "Template is Vite + React JS. Contains index.html, vite.config.js, src/main.jsx, src/App.jsx."
        ),
        ProjectType.VITE_REACT_TAILWIND: (
            "Template is Vite + React TS + Tailwind. Contains index.html, vite.config.ts, tailwind.config.js, src/main.tsx, src/App.tsx. Tailwind is already set up."
        ),
        ProjectType.VANILLA: (
            "Template is plain HTML/CSS/JS."
        ),
    }
    return hints.get(project_type, "Template is standard boilerplate.")
