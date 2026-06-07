import shutil
import unittest
from pathlib import Path

from backend.orchestrator.task_graph import ExecutionTask, TaskGraph
from backend.validation.feature_contracts import (
    FeatureContractContext,
    FeatureDescriptor,
    FeatureManifest,
    extract_features,
    feature_manifest_path,
    load_feature_manifest,
    save_feature_manifest,
)


class SignatureStub:
    app_type = "todo"
    domain = "utility"
    feature_keywords = ["tasks"]
    required_capabilities = ["state_management"]


class TestFeatureExtraction(unittest.TestCase):
    def setUp(self):
        self.project_id = "feature_extraction_test"
        self.workspace = Path("workspaces") / self.project_id
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_extracts_features_from_task_descriptions(self):
        graph = TaskGraph()
        graph.add_task(
            ExecutionTask(
                id="task-1",
                title="Add edit functionality",
                description="Allow editing existing tasks",
                affected_files=["src/TodoList.tsx"],
            )
        )
        graph.add_task(
            ExecutionTask(
                id="task-2",
                title="Remove completed task",
                description="Delete a task from local state",
                affected_files=["src/TodoList.tsx"],
            )
        )
        graph.add_task(
            ExecutionTask(
                id="task-3",
                title="Persist task data",
                description="Save tasks to localStorage",
                affected_files=["src/TodoList.tsx"],
            )
        )

        manifest = extract_features(
            project_id=self.project_id,
            run_id="run_feature_extraction",
            prompt="buat todo list",
            generation_signature=SignatureStub(),
            task_graph=graph,
            project_state={},
        )
        feature_ids = {feature.id for feature in manifest.features}

        self.assertEqual(manifest.app_type, "todo")
        self.assertIn("edit_task", feature_ids)
        self.assertIn("delete_task", feature_ids)
        self.assertIn("persist_task", feature_ids)

    def test_unknown_feature_fallback_when_no_signal(self):
        manifest = extract_features(
            project_id=self.project_id,
            run_id="run_unknown",
            prompt="",
            generation_signature=None,
            task_graph=None,
            project_state={},
        )

        self.assertEqual([feature.id for feature in manifest.features], ["unknown_feature"])
        self.assertEqual(manifest.features[0].confidence, 0.0)

    def test_save_and_load_feature_manifest(self):
        manifest = FeatureManifest(
            project_id=self.project_id,
            run_id="run_manifest",
            app_type="inventory",
            domain="inventory",
            features=[
                FeatureDescriptor("create_item", "create", 0.9, "test"),
                FeatureDescriptor("adjust_stock", "update", 0.8, "test"),
            ],
        )

        path = save_feature_manifest(self.project_id, manifest)
        loaded = load_feature_manifest(self.project_id)

        self.assertEqual(path, feature_manifest_path(self.project_id))
        self.assertTrue(path.exists())
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.app_type, "inventory")
        self.assertEqual([feature.id for feature in loaded.features], ["create_item", "adjust_stock"])

    def test_context_accepts_feature_manifest(self):
        manifest = FeatureManifest(
            project_id=self.project_id,
            run_id="run_context",
            features=[FeatureDescriptor("unknown_feature")],
        )
        context = FeatureContractContext(
            project_id=self.project_id,
            run_id="run_context",
            preview_url="http://127.0.0.1:3000",
            prompt="test",
            feature_manifest=manifest,
        )

        self.assertEqual(context.feature_manifest.features[0].id, "unknown_feature")


if __name__ == "__main__":
    unittest.main()
