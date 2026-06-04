import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from backend.reflection.reflection_engine import ReflectionEngine, REFLECTION_RELATIVE_PATH


class TestReflectionEngine(unittest.TestCase):
    def setUp(self):
        self.project_id = f"refl_{uuid4().hex[:8]}"
        self.workspace = Path("workspaces") / self.project_id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.run_id = "run_20260604_000000_test"

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_reflection_chain_validation_to_learning(self):
        failed_build = SimpleNamespace(
            success=False,
            command="build",
            exit_code=1,
            stdout="",
            stderr="src/App.tsx:1:1 - error TS2307: Cannot find module 'react-router-dom'",
            error=None,
        )
        validation = ReflectionEngine.record_validation(self.project_id, self.run_id, "build", failed_build)
        self.assertEqual(validation["status"], "failed")

        artifact = ReflectionEngine.load(self.project_id)
        self.assertTrue((self.workspace / REFLECTION_RELATIVE_PATH).exists())
        self.assertTrue(artifact["maturity"]["level_1_validation_engine"])
        self.assertTrue(artifact["maturity"]["level_2_error_collector"])
        self.assertTrue(artifact["maturity"]["level_3_root_cause_analyzer"])
        self.assertTrue(artifact["maturity"]["level_4_repair_planner"])
        latest = artifact["cycles"][-1]
        self.assertEqual(latest["errors"][0]["code"], "TS2307")
        self.assertEqual(latest["root_cause"]["category"], "missing_dependency_or_bad_import")
        self.assertGreater(latest["root_cause"]["confidence"], 0.8)
        self.assertGreater(len(latest["repair_plan"]), 0)

        ReflectionEngine.record_repair_execution(
            self.project_id,
            self.run_id,
            success=True,
            attempt=1,
            patched_files=["src/App.tsx"],
            message="Replaced undeclared router import with local state navigation.",
        )
        passed_build = SimpleNamespace(
            success=True,
            command="build",
            exit_code=0,
            stdout="build succeeded",
            stderr="",
            error=None,
        )
        artifact = ReflectionEngine.record_revalidation(self.project_id, self.run_id, passed_build)
        latest = artifact["cycles"][-1]
        self.assertEqual(latest["revalidation"]["status"], "passed")
        self.assertEqual(latest["learning"]["outcome"], "passed")
        self.assertTrue(artifact["maturity"]["level_5_repair_executor"])
        self.assertTrue(artifact["maturity"]["level_6_revalidation_engine"])
        self.assertTrue(artifact["maturity"]["level_7_learning_capture"])
        self.assertGreaterEqual(artifact["reflection_score"]["score"], 90)

    def test_predictive_reflection_records_risk(self):
        prediction = ReflectionEngine.predictive_reflection(
            self.project_id,
            "tambahkan auth role manager",
            {"impact_analysis": {"risk": "high", "confidence": 0.76, "affected_files": ["src/App.tsx"]}},
        )
        self.assertEqual(prediction["risk"], "high")
        artifact = ReflectionEngine.load(self.project_id)
        self.assertTrue(artifact["maturity"]["predictive_reflection"])
        self.assertEqual(artifact["predictive_reflection"]["risk"], "high")


if __name__ == "__main__":
    unittest.main()
