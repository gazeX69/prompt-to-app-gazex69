from backend.core.skills.interfaces import SkillMetadata, CommandStrategy, PreviewStrategy
from backend.core.skills.modular_skill import ModularSkill, ExecutionConstraints, VerificationStrategy

class ReactViteSkill(ModularSkill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="react-vite",
            type="framework",
            language="typescript",
            capabilities=["create", "scan", "modify", "fix"],
            tags=["react", "vite", "frontend", "spa"],
            description="React + Vite frontend application",
        )

    async def can_handle(self, context: dict) -> bool:
        framework = context.get("framework", "")
        tags = context.get("tags", [])
        return framework == "react-vite" or "react" in tags or "vite" in tags

    async def execute(self, context: dict) -> dict:
        return {"skill": "react-vite", "status": "activated", "context": context}

    def get_command_strategy(self) -> CommandStrategy:
        return CommandStrategy(
            install=["npm", "install", "--no-progress"],
            build=["npm", "run", "build", "--no-progress"],
            dev=["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "{port}"],
            lint=["npm", "run", "lint"],
            test=["npm", "run", "test"],
        )

    def get_preview_strategy(self) -> PreviewStrategy:
        return PreviewStrategy(
            host="127.0.0.1",
            port=0,
            readiness_patterns=[
                r"http://(?:localhost|127\.0\.0\.1):(\d+)",
                r"VITE.*ready",
                r"Local:",
            ],
        )

    def get_system_prompt(self) -> str:
        return (
            "You are a senior frontend engineer generating a React + Vite + TypeScript application.\n"
            "A Vite + React + TypeScript + TailwindCSS project has already been scaffolded.\n"
            "Generate feature files overwriting the defaults (src/App.tsx, etc.) and adding new ones.\n"
            "Rules:\n"
            "- Use React 18 compatible code (functional components, hooks).\n"
            "- Use TypeScript.\n"
            "- Use TailwindCSS for styling.\n"
            "- Return files using ===FILE:relative/path.ext=== ... ===END===\n"
            "- Do NOT generate package.json, vite.config.ts, tsconfig.json, tsconfig.app.json, tsconfig.node.json, index.html, or src/main.tsx.\n"
            "- If you must generate tsconfig files, NEVER use \"moduleResolution\": \"classic\". ALWAYS use \"moduleResolution\": \"bundler\" or \"node\".\n"
            "- Use the dependencies already present in the canonical template.\n"
            "- Import rules: do NOT use path aliases such as \"@/...\".\n"
            "- Use relative imports only, for example \"./types\", \"./utils/storage\", \"./components/ItemForm\", or \"../types\".\n"
            "- Do not import packages, aliases, or modules that are not configured in the canonical template.\n"
        )

    def get_project_structure(self) -> list[str]:
        return [
            "src/App.tsx",
            "src/main.tsx",
            "src/index.css",
            "index.html",
            "package.json",
            "vite.config.ts",
            "tsconfig.json",
            "tsconfig.app.json",
            "tsconfig.node.json",
            "tailwind.config.js",
        ]

    def get_file_patterns(self) -> list[str]:
        return ["*.tsx", "*.ts", "*.jsx", "*.js", "*.css", "*.json", "*.html"]

    def get_required_files_before_install(self) -> list[str]:
        return ["package.json"]

    def get_required_files_before_dev(self) -> list[str]:
        return ["package.json", "index.html"]

    def get_generation_hints(self) -> dict:
        return {
            "requires_template": True,
            "template_name": "vite-react-ts",
            "requires_install": True,
            "requires_build": True,
            "requires_dev_server": True,
        }

    async def get_prompt_modifiers(self) -> list[dict]:
        return [
            {
                "role": "system",
                "content": (
                    "You are generating a React + Vite + TypeScript application. "
                    "Use functional components, hooks, and TailwindCSS. "
                    "Do not use path aliases such as '@/...'; use relative imports only."
                ),
            }
        ]

    async def get_detection_hints(self) -> dict:
        return {
            "config_files": ["vite.config.ts", "vite.config.js", "tailwind.config.js"],
            "package_patterns": {"dependencies": ["react", "react-dom"], "devDependencies": ["vite"]},
        }

    def get_execution_constraints(self) -> ExecutionConstraints:
        return ExecutionConstraints(
            requires_build=True,
            requires_dependencies=True,
            isolated_cwd=True,
            allowed_file_patterns=self.get_file_patterns()
        )

    def get_verification_strategy(self) -> VerificationStrategy:
        return VerificationStrategy(
            verify_html=True,
            verify_source_marker=True,
            verify_dom=True,
            success_criteria=["runtime_truth_marker", "http_200"],
            timeout_ms=15000
        )

    def get_planning_capabilities(self) -> list[str]:
        return ["scaffold_spa", "react_components", "tailwind_styling"]
