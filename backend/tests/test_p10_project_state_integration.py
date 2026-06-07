import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.brain.change_scope import CHANGE_SCOPE_RELATIVE_PATH, ChangeScopeAnalyzer
from backend.brain.discovery_tree.discovery_engine import answer_discovery, start_discovery
from backend.brain.schemas import PreflightRequest
from backend.memory.project_memory import PROJECT_STATE_RELATIVE_PATH, ProjectMemory
from backend.memory.workspace_awareness import WorkspaceAwareness
from backend.reflection.reflection_engine import ReflectionEngine
from backend.routes.brain import preflight


class TestP10ProjectStateIntegration(unittest.TestCase):
    def setUp(self):
        self.project_id = f"p10c_{uuid4().hex[:8]}"
        self.workspace = Path("workspaces") / self.project_id

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)
        hello_workspace = Path("workspaces") / f"{self.project_id}_hello"
        if hello_workspace.exists():
            shutil.rmtree(hello_workspace)

    def _complete_inventory_discovery(self):
        turn = start_discovery("buat CRUD", project_id=self.project_id)
        turn = answer_discovery(turn.session_id, "inventory", project_id=self.project_id)
        turn = answer_discovery(turn.session_id, "postgres", project_id=self.project_id)
        return answer_discovery(turn.session_id, "ya", project_id=self.project_id)

    def test_discovery_completion_populates_project_state_json(self):
        final_turn = self._complete_inventory_discovery()
        state_path = self.workspace / PROJECT_STATE_RELATIVE_PATH
        state = ProjectMemory.get_project_state(self.project_id)

        self.assertTrue(final_turn.complete)
        self.assertTrue(state_path.exists())
        self.assertEqual(state["project_type"], "crud")
        self.assertEqual(state["domain"], "inventory")
        self.assertEqual(state["database"], "postgres")
        self.assertIs(state["supplier"], True)

    def test_change_scope_uses_project_state_project_type_and_domain(self):
        self._complete_inventory_discovery()
        state = ProjectMemory.load_for(self.project_id, "scope analysis")
        action = ProjectMemory.classify_action(self.project_id, "tambahkan kolom sku")
        scope = ChangeScopeAnalyzer.analyze(
            self.project_id,
            "tambahkan kolom sku",
            project_state=state,
            project_action=action,
            workspace_awareness=None,
        )

        self.assertTrue((self.workspace / CHANGE_SCOPE_RELATIVE_PATH).exists())
        self.assertEqual(scope["project_type"], "crud")
        self.assertEqual(scope["domain"], "inventory")

    def test_workspace_awareness_consumes_project_state(self):
        self._complete_inventory_discovery()
        awareness = WorkspaceAwareness.scan(self.project_id, prompt="buat CRUD inventory")

        self.assertEqual(awareness["project_state"]["project_type"], "crud")
        self.assertEqual(awareness["project_state"]["domain"], "inventory")

    def test_reflection_consumes_project_state_read_only(self):
        self._complete_inventory_discovery()
        awareness = WorkspaceAwareness.scan(self.project_id, prompt="buat CRUD inventory")
        prediction = ReflectionEngine.predictive_reflection(self.project_id, "buat CRUD inventory", awareness)

        self.assertEqual(prediction["project_state"]["project_type"], "crud")
        self.assertEqual(prediction["project_state"]["domain"], "inventory")

    def test_project_state_load_for_generation_traces_and_existing_preflight_still_works(self):
        self._complete_inventory_discovery()
        with self.assertLogs("backend.memory.project_memory", level="INFO") as captured:
            state = ProjectMemory.load_for(self.project_id, "generation")

        logs = "\n".join(captured.output)
        self.assertEqual(state["project_type"], "crud")
        self.assertIn("[ProjectState] Loaded for generation", logs)
        self.assertIn("[ProjectState] project_type=crud", logs)

        result = preflight(PreflightRequest(prompt="buat hello world", project_id=f"{self.project_id}_hello"))
        self.assertIsNone(result.discovery_session)
        self.assertEqual(result.signature.app_type, "hello_world")


if __name__ == "__main__":
    unittest.main()
