import base64
import tempfile
import unittest
from pathlib import Path

from backend.core.scanner import workspace_scanner


def path_id(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("utf-8")


def tree_has_path(nodes, path: str) -> bool:
    for node in nodes:
        if node.get("path") == path:
            return True
        if tree_has_path(node.get("children") or [], path):
            return True
    return False


class ExplorerFileOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original_root = workspace_scanner.get_workspaces_root
        workspace_scanner.get_workspaces_root = lambda: self.root
        self.workspace = self.root / "workspace_a"
        self.run = self.workspace / "run_success"
        self.run.mkdir(parents=True)
        (self.run / "package.json").write_text('{"scripts":{"dev":"vite"}}', encoding="utf-8")
        (self.run / "src").mkdir()
        (self.run / "src" / "App.tsx").write_text("export default function App() { return null }\n", encoding="utf-8")

    def tearDown(self):
        workspace_scanner.get_workspaces_root = self.original_root
        self.tmp.cleanup()

    def test_create_folder_file_read_edit_save(self):
        folder = workspace_scanner.create_workspace_entry("workspace_a", "src/features", "directory", run_id="run_success")
        self.assertTrue(folder["ok"], folder)
        self.assertTrue((self.run / "src" / "features").is_dir())

        created = workspace_scanner.create_workspace_entry(
            "workspace_a",
            "src/features/new.ts",
            "file",
            "export const value = 1\n",
            run_id="run_success",
        )
        self.assertTrue(created["ok"], created)

        loaded = workspace_scanner.get_workspace_file_content("workspace_a", created["pathId"], "run_success")
        self.assertEqual(loaded["content"], "export const value = 1\n")

        saved = workspace_scanner.save_workspace_file_content(
            "workspace_a",
            created["pathId"],
            "export const value = 2\n",
            "run_success",
        )
        self.assertTrue(saved["ok"], saved)
        self.assertEqual((self.run / "src" / "features" / "new.ts").read_text(encoding="utf-8"), "export const value = 2\n")

    def test_rename_move_and_delete_file_update_tree(self):
        created = workspace_scanner.create_workspace_entry("workspace_a", "src/old.ts", "file", "old", "run_success")
        self.assertTrue(created["ok"], created)

        renamed = workspace_scanner.move_workspace_entry("workspace_a", created["pathId"], "src/new.ts", "run_success")
        self.assertTrue(renamed["ok"], renamed)
        self.assertFalse((self.run / "src" / "old.ts").exists())
        self.assertTrue((self.run / "src" / "new.ts").is_file())

        workspace_scanner.create_workspace_entry("workspace_a", "src/moved", "directory", run_id="run_success")
        moved = workspace_scanner.move_workspace_entry("workspace_a", renamed["pathId"], "src/moved/new.ts", "run_success")
        self.assertTrue(moved["ok"], moved)
        self.assertTrue((self.run / "src" / "moved" / "new.ts").is_file())
        refreshed_tree = workspace_scanner.get_workspace_tree("workspace_a", "run_success")
        self.assertTrue(tree_has_path(refreshed_tree["tree"], "src/moved/new.ts"))

        deleted = workspace_scanner.delete_workspace_entry("workspace_a", moved["pathId"], "run_success")
        self.assertTrue(deleted["ok"], deleted)
        self.assertFalse((self.run / "src" / "moved" / "new.ts").exists())
        refreshed_tree = workspace_scanner.get_workspace_tree("workspace_a", "run_success")
        self.assertFalse(tree_has_path(refreshed_tree["tree"], "src/moved/new.ts"))

    def test_rename_move_and_delete_folder(self):
        workspace_scanner.create_workspace_entry("workspace_a", "src/folder", "directory", run_id="run_success")
        nested = workspace_scanner.create_workspace_entry("workspace_a", "src/folder/nested.ts", "file", "nested", "run_success")
        self.assertTrue(nested["ok"], nested)

        renamed = workspace_scanner.move_workspace_entry("workspace_a", path_id("src/folder"), "src/renamed", "run_success")
        self.assertTrue(renamed["ok"], renamed)
        self.assertTrue((self.run / "src" / "renamed" / "nested.ts").is_file())

        workspace_scanner.create_workspace_entry("workspace_a", "src/target", "directory", run_id="run_success")
        moved = workspace_scanner.move_workspace_entry("workspace_a", renamed["pathId"], "src/target/renamed", "run_success")
        self.assertTrue(moved["ok"], moved)
        self.assertTrue((self.run / "src" / "target" / "renamed" / "nested.ts").is_file())

        deleted = workspace_scanner.delete_workspace_entry("workspace_a", moved["pathId"], "run_success")
        self.assertTrue(deleted["ok"], deleted)
        self.assertFalse((self.run / "src" / "target" / "renamed").exists())

    def test_operations_reject_traversal_blocked_segments_and_overwrite(self):
        traversal = workspace_scanner.create_workspace_entry("workspace_a", "../escape.ts", "file", "", "run_success")
        self.assertFalse(traversal["ok"])
        self.assertIn("traversal", traversal["error"])

        blocked = workspace_scanner.create_workspace_entry("workspace_a", "node_modules/x.ts", "file", "", "run_success")
        self.assertFalse(blocked["ok"])
        self.assertIn("not editable", blocked["error"])

        overwrite = workspace_scanner.create_workspace_entry("workspace_a", "src/App.tsx", "file", "", "run_success")
        self.assertFalse(overwrite["ok"])
        self.assertIn("already exists", overwrite["error"])

    def test_operations_stay_in_requested_run(self):
        other_run = self.workspace / "run_other"
        (other_run / "src").mkdir(parents=True)
        (other_run / "package.json").write_text("{}", encoding="utf-8")
        (other_run / "src" / "App.tsx").write_text("other", encoding="utf-8")

        created = workspace_scanner.create_workspace_entry("workspace_a", "src/only-success.ts", "file", "success", "run_success")
        self.assertTrue(created["ok"], created)
        self.assertTrue((self.run / "src" / "only-success.ts").is_file())
        self.assertFalse((other_run / "src" / "only-success.ts").exists())


if __name__ == "__main__":
    unittest.main()
