import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.brain.discovery_tree.discovery_engine import answer_discovery, restore_discovery, start_discovery
from backend.routes.brain import preflight
from backend.brain.schemas import PreflightRequest


class TestDiscoveryTree(unittest.TestCase):
    def setUp(self):
        self.project_id = f"p10_discovery_{uuid4().hex[:8]}"
        self.workspace = Path("workspaces") / self.project_id

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_crud_prompt_starts_with_domain_question(self):
        result = preflight(PreflightRequest(prompt="buat CRUD", project_id=self.project_id))

        self.assertIsNotNone(result.discovery_session)
        self.assertEqual(result.discovery_session["question"], "CRUD untuk kasus apa?")
        self.assertEqual(result.scope_analysis.missing_decisions[0].question, "CRUD untuk kasus apa?")

    def test_inventory_answer_moves_to_database_question(self):
        turn = start_discovery("buat CRUD", project_id=self.project_id)
        next_turn = answer_discovery(turn.session_id, "inventory", project_id=self.project_id)

        self.assertEqual(next_turn.current_node, "crud_inventory")
        self.assertEqual(next_turn.question, "Database apa?")
        self.assertEqual(next_turn.answers["domain"], "inventory")

    def test_postgres_answer_moves_to_supplier_question(self):
        turn = start_discovery("buat CRUD", project_id=self.project_id)
        next_turn = answer_discovery(turn.session_id, "inventory", project_id=self.project_id)
        supplier_turn = answer_discovery(next_turn.session_id, "postgres", project_id=self.project_id)

        self.assertEqual(supplier_turn.current_node, "crud_inventory_supplier")
        self.assertEqual(supplier_turn.question, "Perlu supplier?")
        self.assertEqual(supplier_turn.answers["database"], "postgres")

    def test_discovery_complete_builds_project_state_draft_and_restores(self):
        turn = start_discovery("buat CRUD", project_id=self.project_id)
        turn = answer_discovery(turn.session_id, "inventory", project_id=self.project_id)
        turn = answer_discovery(turn.session_id, "postgres", project_id=self.project_id)
        final_turn = answer_discovery(turn.session_id, "ya", project_id=self.project_id)
        restored = restore_discovery(final_turn.session_id, project_id=self.project_id)

        self.assertTrue(final_turn.complete)
        self.assertEqual(final_turn.draft_state["project_type"], "crud")
        self.assertEqual(final_turn.draft_state["domain"], "inventory")
        self.assertEqual(final_turn.draft_state["database"], "postgres")
        self.assertIs(final_turn.draft_state["supplier"], True)
        self.assertEqual(restored.draft_state, final_turn.draft_state)


if __name__ == "__main__":
    unittest.main()
