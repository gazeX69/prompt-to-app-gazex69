import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.brain.plan_signature import build_plan_signature
from backend.brain.schemas import BrainDecision, PreflightRequest
from backend.brain.change_scope import ChangeScopeAnalyzer, CHANGE_SCOPE_RELATIVE_PATH
from backend.memory.project_memory import ProjectMemory, PROJECT_STATE_RELATIVE_PATH
from backend.memory.workspace_awareness import WorkspaceAwareness
from backend.orchestrator.project_orchestrator import (
    _initialize_modify_run_from_current_state,
    _sync_run_to_latest,
)
from backend.routes.brain import preflight


class TestProjectState(unittest.TestCase):
    def setUp(self):
        self.project_id = f"p9_state_{uuid4().hex[:8]}"
        self.workspace = Path("workspaces") / self.project_id

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_p9_a1_state_file_is_created_and_persistent(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        state_path = self.workspace / PROJECT_STATE_RELATIVE_PATH
        self.assertTrue(state_path.exists())

        state = ProjectMemory.get_project_state(self.project_id)
        self.assertEqual(state["project_id"], self.project_id)
        self.assertEqual(state["ecosystem"], "react-vite")

        loaded_again = ProjectMemory.load_project_state(self.project_id)
        self.assertEqual(loaded_again["project_id"], self.project_id)

    def test_p9_a2_to_a6_updates_action_and_preserves_features(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        marketplace_sig = build_plan_signature("buat aplikasi marketplace")
        state = ProjectMemory.update_after_generation(
            self.project_id,
            "buat aplikasi marketplace",
            signature=marketplace_sig,
            ecosystem="react-vite",
            success=True,
        )
        self.assertEqual(state["project_type"], "marketplace")
        self.assertIn("products", state["features"])
        self.assertIn("cart", state["features"])

        action = ProjectMemory.classify_action(self.project_id, "tambahkan wishlist")
        self.assertEqual(action["action"], "modify")
        self.assertIn("wishlist", action["missing_features"])

        wishlist_sig = build_plan_signature("tambahkan wishlist")
        updated = ProjectMemory.update_after_generation(
            self.project_id,
            "tambahkan wishlist",
            signature=wishlist_sig,
            ecosystem="react-vite",
            success=True,
        )
        self.assertIn("products", updated["features"])
        self.assertIn("cart", updated["features"])
        self.assertIn("wishlist", updated["features"])

        duplicate = ProjectMemory.classify_action(self.project_id, "tambahkan cart")
        self.assertEqual(duplicate["action"], "modify")
        self.assertIn("cart", duplicate["duplicate_features"])

    def test_p9_a7_describe_project(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        sig = build_plan_signature("buat aplikasi marketplace")
        ProjectMemory.update_after_generation(
            self.project_id,
            "buat aplikasi marketplace dengan localStorage",
            signature=sig,
            ecosystem="react-vite",
            success=True,
        )
        description = ProjectMemory.describe_project(self.project_id)
        self.assertIn("summary", description)
        self.assertIn("marketplace", description["summary"].lower())
        self.assertGreater(description["confidence"], 0.5)

    def test_state_driven_preflight_treats_background_change_as_modify(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "App.tsx").write_text("export default function App(){ return <h1>Hello World</h1> }\n", encoding="utf-8")
        (self.workspace / "src" / "index.css").write_text("body { margin: 0; }\n", encoding="utf-8")
        (self.workspace / "package.json").write_text('{"dependencies":{"react":"latest","vite":"latest"},"scripts":{"build":"vite build"}}\n', encoding="utf-8")
        hello_sig = build_plan_signature("buat hello world")
        ProjectMemory.update_after_generation(
            self.project_id,
            "buat hello world",
            signature=hello_sig,
            ecosystem="react-vite",
            success=True,
        )

        result = preflight(PreflightRequest(
            prompt="buat backgroundnya menjadi biru",
            project_id=self.project_id,
        ))

        self.assertEqual(result.project_action["action"], "modify")
        self.assertEqual(result.decision, BrainDecision.LOCAL_ONLY)
        self.assertFalse(result.planning_required)
        self.assertFalse(result.scope_analysis.is_broad)
        self.assertEqual(result.scope_analysis.risk_level, "low")
        self.assertEqual(result.scope_analysis.missing_decisions, [])
        self.assertEqual(result.signature.app_type, "hello_world")
        self.assertEqual(result.signature.required_capabilities, ["style_update"])
        self.assertIsNotNone(result.change_scope)
        self.assertEqual(result.change_scope["scope_size"], "small")
        self.assertEqual(result.change_scope["change_type"], "style_update")
        self.assertIn("preview_visual_check", result.change_scope["required_validation"])
        self.assertTrue(
            "src/index.css" in result.change_scope["target_files"]
            or "src/App.tsx" in result.change_scope["target_files"]
        )
        self.assertNotEqual(result.recommended_mvp.title, "CRUD MVP")

    def test_change_scope_content_addition_preserves_existing_state(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "App.tsx").write_text("export default function App(){ return <h1>Hello World</h1> }\n", encoding="utf-8")
        (self.workspace / "src" / "index.css").write_text("body { background: green; }\n", encoding="utf-8")
        (self.workspace / "package.json").write_text('{"dependencies":{"react":"latest","vite":"latest"},"scripts":{"build":"vite build"}}\n', encoding="utf-8")
        hello_sig = build_plan_signature("buat hello world")
        ProjectMemory.update_after_generation(
            self.project_id,
            "buat hello world",
            signature=hello_sig,
            ecosystem="react-vite",
            success=True,
        )

        result = preflight(PreflightRequest(
            prompt="tambahkan tulisan hello dunia di bawah nya",
            project_id=self.project_id,
        ))

        self.assertEqual(result.decision, BrainDecision.LOCAL_ONLY)
        self.assertEqual(result.change_scope["scope_size"], "small")
        self.assertEqual(result.change_scope["change_type"], "content_addition")
        self.assertIn("src/App.tsx", result.change_scope["target_files"])
        self.assertIn("preview_visual_check", result.change_scope["required_validation"])
        preserved = result.change_scope["preserved_source_facts"]["relevant_preservation_facts"]
        self.assertTrue(any("green" in fact or "hijau" in fact for fact in preserved))
        self.assertEqual(result.scope_analysis.missing_decisions, [])
        self.assertTrue((self.workspace / CHANGE_SCOPE_RELATIVE_PATH).exists())

    def test_modify_run_starts_from_latest_state_and_syncs_back(self):
        latest = self.workspace / "latest"
        (latest / "src").mkdir(parents=True, exist_ok=True)
        (latest / "src" / "App.tsx").write_text("export default function App(){ return <h1>Hello World</h1> }\n", encoding="utf-8")
        (latest / "src" / "index.css").write_text("body { background: green; color: white; }\n", encoding="utf-8")
        (latest / "package.json").write_text('{"dependencies":{"react":"latest","vite":"latest"},"scripts":{"build":"vite build"}}\n', encoding="utf-8")

        ProjectMemory.initialize_project(self.project_id, "react-vite")
        hello_sig = build_plan_signature("buat hello world")
        ProjectMemory.update_after_generation(
            self.project_id,
            "buat hello world",
            signature=hello_sig,
            ecosystem="react-vite",
            success=True,
        )
        action = ProjectMemory.classify_action(self.project_id, "tambahkan tulisan hello dunia dibawahnya")
        run_id = "run_preserve_green"

        copied = _initialize_modify_run_from_current_state(self.project_id, run_id, action)

        self.assertTrue(copied)
        run_css = self.workspace / run_id / "src" / "index.css"
        self.assertIn("background: green", run_css.read_text(encoding="utf-8"))

        run_css.write_text("body { background: green; color: white; }\n.hero { padding: 24px; }\n", encoding="utf-8")
        synced = _sync_run_to_latest(self.project_id, run_id)

        self.assertTrue(synced)
        self.assertIn(".hero", (latest / "src" / "index.css").read_text(encoding="utf-8"))

    def test_change_scope_preserves_green_background_fact_for_content_addition(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        (self.workspace / "src").mkdir(parents=True, exist_ok=True)
        (self.workspace / "src" / "App.tsx").write_text("export default function App(){ return <h1>Hello World</h1> }\n", encoding="utf-8")
        (self.workspace / "src" / "index.css").write_text("body { background: green; color: white; }\n", encoding="utf-8")
        (self.workspace / "package.json").write_text('{"dependencies":{"react":"latest","vite":"latest"},"scripts":{"build":"vite build"}}\n', encoding="utf-8")
        sig = build_plan_signature("buat hello world")
        ProjectMemory.update_after_generation(
            self.project_id,
            "buat hello world",
            signature=sig,
            ecosystem="react-vite",
            success=True,
        )
        awareness = WorkspaceAwareness.scan(self.project_id, prompt="tambahkan tulisan hello dunia dibawahnya")
        scope = ChangeScopeAnalyzer.analyze(
            self.project_id,
            "tambahkan tulisan hello dunia dibawahnya",
            project_state=ProjectMemory.get_project_state(self.project_id),
            project_action=ProjectMemory.classify_action(self.project_id, "tambahkan tulisan hello dunia dibawahnya"),
            workspace_awareness=awareness,
        )

        self.assertEqual(scope["scope_size"], "small")
        self.assertEqual(scope["change_type"], "content_addition")
        facts = scope["preserved_source_facts"]["relevant_preservation_facts"]
        constraints = scope["preservation_constraints"]
        self.assertTrue(any("background = green" in fact for fact in facts))
        self.assertTrue(any("background = green" in item for item in constraints))

    def test_change_scope_broad_modify_requires_narrowing_questions(self):
        ProjectMemory.initialize_project(self.project_id, "react-vite")
        hello_sig = build_plan_signature("buat hello world")
        ProjectMemory.update_after_generation(
            self.project_id,
            "buat hello world",
            signature=hello_sig,
            ecosystem="react-vite",
            success=True,
        )

        result = preflight(PreflightRequest(
            prompt="rombak arsitektur lengkap dengan auth role manager dan backend",
            project_id=self.project_id,
        ))

        self.assertEqual(result.project_action["action"], "modify")
        self.assertIn(result.change_scope["scope_size"], {"medium", "large", "unclear"})
        self.assertTrue(result.change_scope["should_ask_clarification"])
        self.assertGreater(len(result.change_scope["clarifying_questions"]), 0)
        self.assertGreater(len(result.scope_analysis.missing_decisions), 0)
        self.assertNotEqual(result.decision, BrainDecision.LOCAL_ONLY)


if __name__ == "__main__":
    unittest.main()
