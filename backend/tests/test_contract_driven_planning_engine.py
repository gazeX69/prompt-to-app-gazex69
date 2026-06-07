import asyncio
import unittest
from unittest.mock import patch

from backend.brain.plan_signature import build_plan_signature
from backend.orchestrator.planning_engine import PlanningEngine
from backend.orchestrator.project_mapper import ProjectMap


FORBIDDEN_MARKETPLACE_TITLES = {
    "Create marketplace landing page structure",
    "Add navigation bar component",
    "Add user authentication flow",
    "Optimize performance with Vite",
}


class TestContractDrivenPlanningEngine(unittest.TestCase):
    def _project_map(self) -> ProjectMap:
        return ProjectMap(
            project_id="contract_planning_test",
            run_id="run_test",
            ecosystem="react-vite",
            frameworks=["react", "vite"],
            entrypoints=["src/App.tsx"],
            dependencies={"react": "latest", "vite": "latest"},
        )

    def _create_plan(self, prompt: str):
        return asyncio.run(PlanningEngine.create_plan(prompt, "React + Vite", self._project_map()))

    def test_marketplace_uses_contract_task_templates_without_llm(self):
        with patch("backend.orchestrator.planning_engine.complete", side_effect=AssertionError("LLM planner should not run")):
            with self.assertLogs("backend.orchestrator.planning_engine", level="INFO") as logs:
                graph = self._create_plan("buat marketplace modern")

        self.assertEqual(
            list(graph.tasks.keys()),
            [
                "types_and_seed_data",
                "marketplace_store",
                "marketplace_components",
                "compose_marketplace_app",
            ],
        )
        titles = {task.title for task in graph.tasks.values()}
        self.assertEqual(
            titles,
            {
                "Define marketplace data model",
                "Create marketplace state store",
                "Build marketplace UI components",
                "Compose marketplace app shell",
            },
        )
        self.assertTrue(FORBIDDEN_MARKETPLACE_TITLES.isdisjoint(titles))
        joined_logs = "\n".join(logs.output)
        self.assertIn("[Planning] contract_deterministic_plan_used app_type=marketplace domain=marketplace tasks=4", joined_logs)
        self.assertNotIn("[Planning] llm_planner_used app_type=marketplace", joined_logs)

    def test_inventory_uses_contract_task_templates_without_llm(self):
        with patch("backend.orchestrator.planning_engine.complete", side_effect=AssertionError("LLM planner should not run")):
            graph = self._create_plan("buat sistem inventory gudang")

        self.assertEqual(
            list(graph.tasks.keys()),
            [
                "inventory_types",
                "inventory_store",
                "inventory_components",
                "compose_inventory_app",
            ],
        )

    def test_crud_app_uses_contract_task_templates_without_llm(self):
        with patch("backend.orchestrator.planning_engine.complete", side_effect=AssertionError("LLM planner should not run")):
            graph = self._create_plan("buat CRUD produk")

        self.assertEqual(
            list(graph.tasks.keys()),
            [
                "crud_types",
                "crud_store",
                "crud_components",
                "compose_crud_app",
            ],
        )

    def test_unknown_domain_is_not_forced_to_crud_app(self):
        signature = build_plan_signature("buat website company profile modern")
        self.assertEqual(signature.domain, "UNKNOWN_DOMAIN")
        self.assertEqual(signature.app_type, "unknown_domain")

        llm_response = """
        [
          {
            "id": "company_profile_llm_plan",
            "title": "Plan company profile website",
            "description": "Create a safe exploratory plan for an unknown domain.",
            "dependencies": [],
            "affected_files": ["src/App.tsx"],
            "allowed_write_paths": ["src/App.tsx"],
            "forbidden_paths": ["package.json"],
            "success_criteria": ["company profile plan exists"],
            "patches": []
          }
        ]
        """
        with patch("backend.orchestrator.planning_engine.complete", return_value=llm_response) as complete_mock:
            with self.assertLogs("backend.orchestrator.planning_engine", level="INFO") as logs:
                graph = self._create_plan("buat website company profile modern")

        complete_mock.assert_called_once()
        self.assertEqual(list(graph.tasks.keys()), ["company_profile_llm_plan"])
        joined_logs = "\n".join(logs.output)
        self.assertIn("[Planning] llm_planner_used app_type=unknown_domain domain=UNKNOWN_DOMAIN reason=unknown_domain", joined_logs)


if __name__ == "__main__":
    unittest.main()
