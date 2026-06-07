import unittest
import os
import json
import shutil
import time
from pathlib import Path
from backend.sandbox.executor import (
    RuntimeEntry,
    MockPopen,
    _runtime_registry,
    _runtime_status_snapshots,
    _session_file_path,
    _save_session_to_disk,
    _delete_session_from_disk,
    recover_sessions_from_disk,
    recover_single_session_from_disk,
    get_runtime_status,
    _normalize_vite_dev_command_args,
    _record_runtime_status,
    validate_node_runtime_contract,
    WORKSPACE_ROOT,
)
from backend.core.skills.builtin.laravel import LaravelSkill
from backend.routes.runtime import _resolve_runtime_run_id

class TestRuntimeRecovery(unittest.TestCase):
    def setUp(self):
        # Create a mock workspace directory if it doesn't exist
        self.project_id = f"test_recovery_project_{self._testMethodName}"
        self.project_dir = WORKSPACE_ROOT / self.project_id
        self.project_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup existing registry entry for safety
        self.saved_entry = _runtime_registry.pop(self.project_id, None)
        self.saved_snapshot = _runtime_status_snapshots.pop(self.project_id, None)

    def tearDown(self):
        # Cleanup mock files
        session_file = _session_file_path(self.project_id)
        if session_file.is_file():
            for _ in range(5):
                try:
                    session_file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.05)
        
        dot_ai_agent = self.project_dir / ".ai-agent"
        if dot_ai_agent.is_dir():
            try:
                shutil.rmtree(dot_ai_agent)
            except Exception:
                pass

        run_node = self.project_dir / "run_node"
        if run_node.is_dir():
            try:
                shutil.rmtree(run_node)
            except Exception:
                pass

        run_vite = self.project_dir / "run_vite"
        if run_vite.is_dir():
            try:
                shutil.rmtree(run_vite)
            except Exception:
                pass

        run_selected_failed = self.project_dir / "run_selected_failed"
        if run_selected_failed.is_dir():
            try:
                shutil.rmtree(run_selected_failed)
            except Exception:
                pass
                
        if self.project_dir.is_dir():
            try:
                # Only remove if it's empty
                self.project_dir.rmdir()
            except Exception:
                pass

        # Restore original registry entry
        if self.saved_entry:
            _runtime_registry[self.project_id] = self.saved_entry
        else:
            _runtime_registry.pop(self.project_id, None)

        if self.saved_snapshot:
            _runtime_status_snapshots[self.project_id] = self.saved_snapshot
        else:
            _runtime_status_snapshots.pop(self.project_id, None)

    def test_save_and_delete_session(self):
        entry = RuntimeEntry(
            project_id=self.project_id,
            run_id="run_001",
            process_pid=12345,
            cwd=str(self.project_dir.resolve()),
            assigned_port="3015",
            started_at=1234567.8,
            runtime_type="dev_server",
            preview_url="http://127.0.0.1:3015",
            process_status="running",
            popen=MockPopen(12345)
        )
        
        # Test saving
        _save_session_to_disk(entry)
        session_file = _session_file_path(self.project_id)
        self.assertTrue(session_file.is_file())
        
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        self.assertEqual(data["project_id"], self.project_id)
        self.assertEqual(data["pid"], 12345)
        self.assertEqual(data["status"], "RUNNING")

        # Test deleting
        _delete_session_from_disk(self.project_id)
        self.assertFalse(session_file.is_file())

    def test_recover_active_alive_session(self):
        # We use os.getpid() as it is guaranteed to be alive
        my_pid = os.getpid()
        entry = RuntimeEntry(
            project_id=self.project_id,
            run_id="run_active",
            process_pid=my_pid,
            cwd=str(self.project_dir.resolve()),
            assigned_port="3016",
            started_at=1234567.8,
            runtime_type="dev_server",
            preview_url="http://127.0.0.1:3016",
            process_status="running",
            popen=MockPopen(my_pid)
        )
        
        _save_session_to_disk(entry)
        
        # Make sure registry is empty for this project
        _runtime_registry.pop(self.project_id, None)
        
        # Run recovery
        recover_single_session_from_disk(self.project_id)
        
        # Should be loaded into registry
        recovered = _runtime_registry.get(self.project_id)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.process_pid, my_pid)
        self.assertEqual(recovered.process_status, "RUNNING")
        self.assertEqual(recovered.assigned_port, "3016")

    def test_recover_active_dead_session(self):
        # Use an extremely large pid that is highly unlikely to be alive (999999)
        dead_pid = 999999
        entry = RuntimeEntry(
            project_id=self.project_id,
            run_id="run_dead",
            process_pid=dead_pid,
            cwd=str(self.project_dir.resolve()),
            assigned_port="3017",
            started_at=1234567.8,
            runtime_type="dev_server",
            preview_url="http://127.0.0.1:3017",
            process_status="running",
            popen=MockPopen(dead_pid)
        )
        
        _save_session_to_disk(entry)
        
        # Make sure registry is empty
        _runtime_registry.pop(self.project_id, None)
        
        # Run recovery
        recover_single_session_from_disk(self.project_id)
        
        # Should NOT be loaded into registry, but session remains durable as CRASHED
        recovered = _runtime_registry.get(self.project_id)
        self.assertIsNone(recovered)
        
        session_file = _session_file_path(self.project_id)
        self.assertTrue(session_file.is_file())
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "CRASHED")

    def test_record_runtime_status_triggers_save_and_delete(self):
        my_pid = os.getpid()
        entry = RuntimeEntry(
            project_id=self.project_id,
            run_id="run_record",
            process_pid=my_pid,
            cwd=str(self.project_dir.resolve()),
            assigned_port="3018",
            started_at=1234567.8,
            runtime_type="dev_server",
            preview_url="http://127.0.0.1:3018",
            process_status="running",
            popen=MockPopen(my_pid)
        )
        
        # Recording a running RuntimeEntry should save it
        _record_runtime_status(entry)
        session_file = _session_file_path(self.project_id)
        self.assertTrue(session_file.is_file())
        
        # Recording a failed status dict should keep it durable
        failed_status = {
            "project_id": self.project_id,
            "run_id": "run_record",
            "status": "FAILED",
            "port": None,
            "pid": my_pid
        }
        _record_runtime_status(failed_status)
        self.assertTrue(session_file.is_file())
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["status"], "FAILED")

    def test_node_runtime_contract_requires_process_env_port(self):
        run_dir = self.project_dir / "run_node"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "package.json").write_text(
            json.dumps({"scripts": {"start": "node index.js"}}),
            encoding="utf-8",
        )
        (run_dir / "index.js").write_text("app.listen(3000)\n", encoding="utf-8")

        self.assertIn(
            "process.env.PORT",
            validate_node_runtime_contract(self.project_id, "run_node"),
        )

        (run_dir / "index.js").write_text(
            "const port = process.env.PORT || 3000;\napp.listen(port)\n",
            encoding="utf-8",
        )
        self.assertIsNone(validate_node_runtime_contract(self.project_id, "run_node"))

    def test_laravel_dev_command_uses_dynamic_port_placeholder(self):
        dev = LaravelSkill().get_command_strategy().dev
        self.assertIn("--port={port}", dev)
        self.assertNotIn("--port=3000", dev)

    def test_vite_command_normalization_removes_duplicate_port(self):
        run_dir = self.project_dir / "run_vite"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "package.json").write_text(
            json.dumps({
                "scripts": {"dev": "vite --port 5173 --host 0.0.0.0 --strictPort --mode development"},
                "devDependencies": {"vite": "^5.0.0"},
            }),
            encoding="utf-8",
        )

        command = _normalize_vite_dev_command_args(
            run_dir,
            ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "3000"],
            3007,
        )

        self.assertEqual(command[:4], ["npm", "exec", "vite", "--"])
        self.assertEqual(command.count("--port"), 1)
        self.assertEqual(command[command.index("--port") + 1], "3007")
        self.assertNotIn("5173", command)
        self.assertEqual(command.count("--strictPort"), 1)
        self.assertIn("--mode", command)
        self.assertIn("development", command)

    def test_runtime_session_persists_output_tails(self):
        entry = RuntimeEntry(
            project_id=self.project_id,
            run_id="run_tail",
            process_pid=12345,
            cwd=str(self.project_dir.resolve()),
            assigned_port="3019",
            started_at=1234567.8,
            runtime_type="dev_server",
            preview_url=None,
            process_status="CRASHED",
            popen=MockPopen(12345),
            error="Dev server crashed (Exit 1)",
            stdout_tail=["ready in 10 ms"],
            stderr_tail=["Error: duplicate option --port"],
        )

        _save_session_to_disk(entry)
        with open(_session_file_path(self.project_id), "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["stdout_tail"], ["ready in 10 ms"])
        self.assertEqual(data["stderr_tail"], ["Error: duplicate option --port"])

    def test_requested_runnable_run_id_is_respected_even_when_not_active_success(self):
        run_dir = self.project_dir / "run_selected_failed"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "package.json").write_text(
            json.dumps({"scripts": {"dev": "vite --host 127.0.0.1"}}),
            encoding="utf-8",
        )

        self.assertEqual(
            _resolve_runtime_run_id(self.project_id, "run_selected_failed"),
            "run_selected_failed",
        )


if __name__ == "__main__":
    unittest.main()
