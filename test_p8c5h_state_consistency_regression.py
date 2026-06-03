import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.core.scanner.run_manifest as run_manifest
import backend.core.scanner.workspace_scanner as workspace_scanner
import backend.routes.runtime as runtime_routes


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_source_run(workspace_root: Path, project_id: str, run_id: str, marker: str) -> None:
    run_root = workspace_root / project_id / run_id
    (run_root / "src").mkdir(parents=True, exist_ok=True)
    (run_root / "package.json").write_text('{"scripts":{"dev":"vite"},"dependencies":{"vite":"latest"}}', encoding="utf-8")
    (run_root / "src" / "App.tsx").write_text(marker, encoding="utf-8")


def _write_manifest(workspace_root: Path, project_id: str, active_run_id: str) -> None:
    manifest_root = workspace_root / project_id / ".ai-agent"
    _write_json(
        manifest_root / "generation_status.json",
        {
            "project_id": project_id,
            "active_run_id": active_run_id,
            "latest_run_id": "run_failed_newer",
            "current_run_id": "run_failed_newer",
            "status": "failed",
        },
    )
    _write_json(
        manifest_root / "runs" / f"{active_run_id}.json",
        {
            "project_id": project_id,
            "run_id": active_run_id,
            "status": "succeeded",
            "active": True,
            "prompt": "active successful app",
        },
    )
    _write_json(
        manifest_root / "runs" / "run_failed_newer.json",
        {
            "project_id": project_id,
            "run_id": "run_failed_newer",
            "status": "failed",
            "active": False,
            "prompt": "failed app",
        },
    )


class P8C5HStateConsistencyRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.tempdir.name) / "workspaces"
        self.workspace_root.mkdir()
        self.patches = [
            patch.object(workspace_scanner, "get_workspaces_root", lambda: self.workspace_root),
            patch.object(run_manifest, "WORKSPACES_ROOT", self.workspace_root),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.tempdir.cleanup()

    def test_repository_hydration_prefers_manifest_active_successful_run(self):
        project_id = "p8c5h_active"
        _write_source_run(self.workspace_root, project_id, "run_success_active", "active tree")
        _write_source_run(self.workspace_root, project_id, "latest", "stale latest tree")
        _write_source_run(self.workspace_root, project_id, "run_failed_newer", "failed newer tree")
        _write_manifest(self.workspace_root, project_id, "run_success_active")

        tree = workspace_scanner.get_workspace_tree(project_id)

        self.assertEqual(tree["runId"], "run_success_active")
        self.assertEqual(tree["totalFiles"], 2)
        self.assertEqual(workspace_scanner.get_latest_run_id(project_id), "run_success_active")

    def test_failed_source_looking_run_does_not_replace_active_successful_tree(self):
        project_id = "p8c5h_failed"
        _write_source_run(self.workspace_root, project_id, "run_success_active", "active tree")
        _write_source_run(self.workspace_root, project_id, "run_failed_newer", "failed newer tree")
        _write_manifest(self.workspace_root, project_id, "run_success_active")

        resolved_run = workspace_scanner.get_run_dir(self.workspace_root / project_id)
        tree = workspace_scanner.get_workspace_tree(project_id)

        self.assertIsNotNone(resolved_run)
        self.assertEqual(resolved_run.name, "run_success_active")
        self.assertEqual(tree["runId"], "run_success_active")

    def test_runtime_start_rejects_requested_run_that_is_not_active_successful(self):
        project_id = "p8c5h_runtime"
        _write_source_run(self.workspace_root, project_id, "run_success_active", "active tree")
        _write_source_run(self.workspace_root, project_id, "run_failed_newer", "failed newer tree")
        _write_manifest(self.workspace_root, project_id, "run_success_active")

        def safe_project_path(project, run_id=None):
            return self.workspace_root / project / run_id if run_id else self.workspace_root / project

        with patch.object(runtime_routes, "_safe_project_path", safe_project_path):
            self.assertEqual(runtime_routes._resolve_runtime_run_id(project_id, None), "run_success_active")
            with self.assertRaisesRegex(ValueError, "active successful run"):
                runtime_routes._resolve_runtime_run_id(project_id, "run_failed_newer")


if __name__ == "__main__":
    unittest.main()
