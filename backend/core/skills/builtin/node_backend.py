from backend.core.skills.interfaces import BaseSkill, SkillMetadata, CommandStrategy, PreviewStrategy


class NodeBackendSkill(BaseSkill):
    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="node-backend",
            type="framework",
            language="typescript",
            capabilities=["create", "scan", "modify", "fix"],
            tags=["node", "express", "backend", "api", "nestjs"],
            description="Node.js backend application (Express, NestJS, etc.)",
        )

    async def can_handle(self, context: dict) -> bool:
        framework = context.get("framework", "")
        tags = context.get("tags", [])
        return any(t in ["node", "express", "nestjs", "backend"] for t in [framework] + tags)

    async def execute(self, context: dict) -> dict:
        return {"skill": "node-backend", "status": "activated", "context": context}

    def get_command_strategy(self) -> CommandStrategy:
        return CommandStrategy(
            install=["npm", "install", "--no-progress"],
            build=None,
            dev=["npm", "run", "dev"],
            lint=None,
            test=["npm", "test"],
        )

    def get_preview_strategy(self) -> PreviewStrategy:
        return PreviewStrategy(
            host="127.0.0.1",
            port=3000,
            readiness_patterns=[
                r"http://(?:localhost|127\.0\.0\.1):(\d+)",
                r"listening",
                r"started",
            ],
        )

    def get_system_prompt(self) -> str:
        return (
            "You are a senior backend engineer generating a Node.js application.\n"
            "Generate server-side code using Express or plain Node.js.\n"
            "Rules:\n"
            "- Use JavaScript or TypeScript.\n"
            "- Generate package.json with required dependencies.\n"
            "- Return files using ===FILE:relative/path.ext=== ... ===END===\n"
            "- Include a server entry point (index.js or server.js), or package.json scripts/main pointing to one.\n"
            "- Do NOT generate React, Vite, or frontend code unless requested."
        )

    def get_project_structure(self) -> list[str]:
        return ["package.json", "index.js or server.js"]

    def get_file_patterns(self) -> list[str]:
        return ["*.js", "*.ts", "*.json", "*.mjs"]

    def get_required_files_before_install(self) -> list[str]:
        return ["package.json"]

    def get_required_files_before_dev(self) -> list[str]:
        return ["package.json"]

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
            "config_files": ["tsconfig.json", "nest-cli.json", "app.js", "server.js", "index.js"],
            "package_patterns": {"dependencies": ["express", "fastify", "koa", "@nestjs/core"]},
        }
