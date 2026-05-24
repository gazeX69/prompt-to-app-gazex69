"""
PHP Basic skill.

Generates plain PHP projects (no framework).
Uses php -S built-in server for development.
No npm, no vite, no React.
"""
from backend.core.skills.interfaces import SkillMetadata, CommandStrategy, PreviewStrategy
from backend.core.skills.modular_skill import ModularSkill, ExecutionConstraints, VerificationStrategy

class PhpBasicSkill(ModularSkill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="php-basic",
            type="language",
            language="php",
            capabilities=["create", "scan", "modify"],
            tags=["php", "backend", "web"],
            description="Plain PHP project with built-in server",
        )

    async def can_handle(self, context: dict) -> bool:
        framework = context.get("framework", "")
        tags = context.get("tags", [])
        return framework == "php" or "php" in tags or "php-basic" in tags

    async def execute(self, context: dict) -> dict:
        return {"skill": "php-basic", "status": "activated", "context": context}

    def get_command_strategy(self) -> CommandStrategy:
        return CommandStrategy(
            install=None,
            build=None,
            dev=["php", "-S", "127.0.0.1:{port}"],
            lint=None,
            test=None,
        )

    def get_preview_strategy(self) -> PreviewStrategy:
        return PreviewStrategy(
            host="127.0.0.1",
            port=0,
            readiness_patterns=[
                r"http://(?:localhost|127\.0\.0\.1):(\d+)",
                r"started",
                r"Development Server",
                r"Listening",
            ],
        )

    def get_system_prompt(self) -> str:
        return (
            "You are a senior backend engineer generating a PHP application.\n"
            "Generate PHP files for a simple web application.\n"
            "Rules:\n"
            "- Use plain PHP 8.x with no framework.\n"
            "- php-basic must render standalone without MySQL/PostgreSQL.\n"
            "- login/register may be static mock/session-based.\n"
            "- do NOT require setup.sql to display the login page.\n"
            "- setup.sql may be generated as optional documentation only.\n"
            "- index.php must render visible HTML without database connection.\n"
            "- Use inline CSS or separate style.css for styling.\n"
            "- Return files using ===FILE:relative/path.ext=== ... ===END===\n"
            "- All paths must be relative to the project root.\n"
            "- Generate index.php as the entry point.\n"
            "- Generate separate .php files for each page/feature.\n"
            "- Include a style.css if visual styling is needed.\n"
            "- Do NOT generate package.json, tsconfig, or any Node.js files.\n"
            "- Do NOT use npm, vite, or any JavaScript build tools."
        )

    def get_project_structure(self) -> list[str]:
        return ["index.php"]

    def get_file_patterns(self) -> list[str]:
        return ["*.php", "*.css", "*.html", "*.js"]

    def get_required_files_before_dev(self) -> list[str]:
        return ["index.php"]

    def get_generation_hints(self) -> dict:
        return {
            "requires_template": False,
            "template_name": "",
            "requires_install": False,
            "requires_build": False,
            "requires_dev_server": True,
        }

    async def get_detection_hints(self) -> dict:
        return {
            "config_files": [],
            "directory_signals": [],
            "file_extensions": [".php"],
        }

    def get_execution_constraints(self) -> ExecutionConstraints:
        return ExecutionConstraints(
            requires_build=False,
            requires_dependencies=False,
            isolated_cwd=True,
            allowed_file_patterns=self.get_file_patterns()
        )

    def get_verification_strategy(self) -> VerificationStrategy:
        return VerificationStrategy(
            verify_html=True,
            verify_source_marker=False,
            verify_dom=True,
            success_criteria=["runtime_truth_marker", "http_200", "has_visible_text", "no_fatal_errors"],
            timeout_ms=15000
        )

    def get_planning_capabilities(self) -> list[str]:
        return ["php_logic", "html_generation", "mock_data"]
