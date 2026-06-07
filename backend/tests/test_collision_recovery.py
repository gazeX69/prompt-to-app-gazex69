import unittest

from backend.orchestrator.generation.collision_recovery_phase import compose_conflicting_file_patches
from backend.orchestrator.patch_engine import PatchOperation


class TestCollisionRecovery(unittest.TestCase):
    def test_stale_anchor_chain_folds_to_single_create_file(self):
        base = PatchOperation(
            operation="create_file",
            target="src/TodoList.tsx",
            content="export default function TodoList() {\n  return <div>Todo List</div>\n}\n",
        )
        first_replace = PatchOperation(
            operation="replace_block",
            target="src/TodoList.tsx",
            find="return <div>Todo List</div>",
            content="return <div><input /><button>Add</button></div>",
        )
        stale_replace = PatchOperation(
            operation="replace_block",
            target="src/TodoList.tsx",
            find="return <div>Todo List</div>",
            content="return <div><input /><button>Add</button><ul /></div>",
        )

        folded, report = compose_conflicting_file_patches(
            "src/TodoList.tsx",
            [("task-001", base), ("task-002", first_replace), ("task-004", stale_replace)],
            ["task-001", "task-002", "task-004"],
        )

        self.assertTrue(report["folded"])
        self.assertTrue(report["stale_anchor"])
        self.assertEqual(len(folded), 1)
        self.assertEqual(folded[0].operation, "create_file")
        self.assertIn("<button>Add</button>", folded[0].content)
        self.assertNotIn("return <div>Todo List</div>", folded[0].content)


if __name__ == "__main__":
    unittest.main()
