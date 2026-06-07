"""
Laravel/PHP skill.

TODO: Full execution implementation pending Laravel scaffolding.
Current state: metadata + detection + routing. Can_handle matches both 'laravel' and 'php' tags.
"""
from backend.core.skills.interfaces import BaseSkill, SkillMetadata, CommandStrategy


class LaravelSkill(BaseSkill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="laravel",
            type="framework",
            language="php",
            capabilities=["scan", "modify"],
            tags=["laravel", "php", "backend", "web"],
            description="Laravel PHP framework (scaffolding not yet implemented — use php-basic for plain PHP)",
        )

    async def can_handle(self, context: dict) -> bool:
        framework = context.get("framework", "")
        tags = context.get("tags", [])
        return framework == "laravel" or "laravel" in tags

    async def execute(self, context: dict) -> dict:
        # TODO: Implement full Laravel scaffolding
        return {"skill": "laravel", "status": "not_implemented", "context": context}

    def get_command_strategy(self) -> CommandStrategy:
        # TODO: Replace with composer/artisan commands when fully implemented
        return CommandStrategy(
            install=["composer", "install"],
            build=None,
            dev=["php", "artisan", "serve", "--host=127.0.0.1", "--port={port}"],
            lint=None,
            test=["./vendor/bin/phpunit"],
        )

    def get_system_prompt(self) -> str:
        return (
            "You are a senior PHP developer generating a Laravel application.\n"
            "Generate Laravel-specific files (controllers, models, views, routes).\n"
            "Rules:\n"
            "- Use Laravel 11 conventions.\n"
            "- Use Eloquent ORM for database.\n"
            "- Use Blade templates for views.\n"
            "- Return files using ===FILE:relative/path.ext=== ... ===END===\n"
            "- All paths must match Laravel directory structure (app/, resources/, routes/, etc.).\n"
            "- Do NOT generate package.json, tsconfig, or any Node.js files unless adding Vite.\n"
            "- Do NOT use React or Vue unless explicitly requested."
        )

    def get_project_structure(self) -> list[str]:
        return [
            "app/Http/Controllers/Controller.php",
            "routes/web.php",
            "resources/views/welcome.blade.php",
        ]

    def get_file_patterns(self) -> list[str]:
        return ["*.php", "*.blade.php", "*.css", "*.yaml", "*.env"]

    def get_generation_hints(self) -> dict:
        return {
            "requires_template": False,
            "template_name": "",
            "requires_install": True,
            "requires_build": False,
            "requires_dev_server": True,
        }

    async def get_detection_hints(self) -> dict:
        return {
            "config_files": ["composer.json", "artisan"],
            "directory_signals": ["app/Http/Controllers", "resources/views", "routes/web.php"],
        }
