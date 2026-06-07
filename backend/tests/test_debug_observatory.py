import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from backend.brain.change_scope import ChangeScopeAnalyzer
from backend.brain.discovery_tree.discovery_engine import answer_discovery, start_discovery
from backend.core.scanner.run_manifest import record_project_generation_status
from backend.memory.project_memory import ProjectMemory
from backend.memory.workspace_awareness import WorkspaceAwareness
from backend.reflection.reflection_engine import ReflectionEngine
from backend.routes.workspaces import get_debug_observatory


class TestDebugObservatory(unittest.TestCase):
    def setUp(self):
        self.project_id = f"p10d_{uuid4().hex[:8]}"
        self.workspace = Path("workspaces") / self.project_id
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "package.json").write_text('{"dependencies":{"react":"latest","vite":"latest"}}\n', encoding="utf-8")
        (self.workspace / "src" / "App.tsx").write_text("export default function App(){ return <h1>Inventory</h1> }\n", encoding="utf-8")

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def _seed_states(self):
        turn = start_discovery("buat CRUD", project_id=self.project_id)
        turn = answer_discovery(turn.session_id, "inventory", project_id=self.project_id)
        turn = answer_discovery(turn.session_id, "postgres", project_id=self.project_id)
        answer_discovery(turn.session_id, "ya", project_id=self.project_id)
        state = ProjectMemory.get_project_state(self.project_id)
        action = ProjectMemory.classify_action(self.project_id, "tambahkan sku")
        awareness = WorkspaceAwareness.scan(self.project_id, prompt="tambahkan sku")
        ChangeScopeAnalyzer.analyze(
            self.project_id,
            "tambahkan sku",
            project_state=state,
            project_action=action,
            workspace_awareness=awareness,
        )
        ReflectionEngine.record_validation(
            self.project_id,
            "run_observatory",
            "build",
            SimpleNamespace(success=False, command="build", exit_code=1, stdout="", stderr="error TS2307: Cannot find module 'x'", error=None),
        )
        record_project_generation_status(
            self.project_id,
            status="failed",
            generation_id="gen_observatory",
            run_id="run_observatory",
            prompt="buat CRUD inventory",
            error="Build failed",
            detail={"stage": "build"},
        )

    def test_debug_observatory_snapshot_aggregates_agent_state(self):
        self._seed_states()

        snapshot = get_debug_observatory(self.project_id)

        self.assertEqual(snapshot["discovery_state"]["draft_state"]["domain"], "inventory")
        self.assertEqual(snapshot["project_state"]["project_type"], "crud")
        self.assertEqual(snapshot["project_state"]["database"], "postgres")
        self.assertTrue(snapshot["state_files"]["project_state"]["exists"])
        self.assertTrue(snapshot["state_files"]["change_scope"]["exists"])
        self.assertTrue(snapshot["state_files"]["workspace_awareness"]["exists"])
        self.assertTrue(snapshot["state_files"]["reflection"]["exists"])
        self.assertTrue(snapshot["state_files"]["generation_status"]["exists"])
        self.assertEqual(snapshot["generator_context"]["final_prompt"], "buat CRUD inventory")
        self.assertEqual(snapshot["generator_context"]["loaded_contract"]["app_type"], "crud_app")
        self.assertTrue(any(item["stage"] == "Generator" and item["status"] == "failed" for item in snapshot["state_flow"]))
        self.assertTrue(any(item["source"] in {"generation", "reflection"} for item in snapshot["error_center"]))


if __name__ == "__main__":
    unittest.main()
