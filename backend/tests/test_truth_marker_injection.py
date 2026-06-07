import unittest
import asyncio
import shutil
from pathlib import Path
from uuid import uuid4

from backend.agent.tools import create_project, write_file
from backend.orchestrator.generation.lifecycle import _sync_run_to_latest
from backend.orchestrator.generation.scaffold_phase import (
    _inject_truth_markers,
    _remove_existing_runtime_truth_markers,
)


class TestTruthMarkerInjection(unittest.TestCase):
    def setUp(self):
        self.project_id = f"marker_test_{uuid4().hex[:8]}"
        self.workspace = Path("workspaces") / self.project_id

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_remove_existing_runtime_truth_marker_before_reinject(self):
        old_run = "run_20260606_123351_23sttp"
        content = f"""import App from './App'

createRoot(document.getElementById('root')!).render(
  <>
      <div id="runtime-truth" data-run-id="{old_run}" data-project-id="demo" style={{ display: "none" }} />
      <App />
    </>
)
"""

        cleaned = _remove_existing_runtime_truth_markers(content)

        self.assertNotIn("runtime-truth", cleaned)
        self.assertNotIn(old_run, cleaned)
        self.assertIn("<App />", cleaned)

    def test_modify_inherited_main_replaces_old_runtime_truth_marker(self):
        run1 = "run_20260606_123351_23sttp"
        run2 = "run_20260606_123512_maaoj5"
        create_project(self.project_id, run2)
        write_file(
            self.project_id,
            "src/main.tsx",
            f"""import App from './App'

createRoot(document.getElementById('root')!).render(
  <>
      <div id="runtime-truth" data-run-id="{run1}" data-project-id="{self.project_id}" style={{ display: "none" }} />
      <App />
    </>
)
""",
            run2,
        )
        write_file(self.project_id, "index.html", "<html><head></head><body><div id=\"root\"></div></body></html>", run2)

        asyncio.run(_inject_truth_markers(self.project_id, run2, "tambahkan teks baru", "react-vite"))
        run2_main = self.workspace / run2 / "src" / "main.tsx"
        main_text = run2_main.read_text(encoding="utf-8")

        self.assertIn(f'data-run-id="{run2}"', main_text)
        self.assertNotIn(f'data-run-id="{run1}"', main_text)
        self.assertEqual(main_text.count("runtime-truth"), 1)

        self.assertTrue(_sync_run_to_latest(self.project_id, run2))
        latest_text = (self.workspace / "latest" / "src" / "main.tsx").read_text(encoding="utf-8")
        self.assertIn(f'data-run-id="{run2}"', latest_text)
        self.assertNotIn(f'data-run-id="{run1}"', latest_text)
        self.assertEqual(latest_text.count("runtime-truth"), 1)


if __name__ == "__main__":
    unittest.main()
