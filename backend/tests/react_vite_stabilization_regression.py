import asyncio
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from backend.models.schemas import GeneratedFile, GenerateRequest
from backend.runtime_contract import RuntimeErrorCode, can_transition, classify_dependency_import, DEPENDENCY_POLICY, error_payload
from backend.orchestrator.project_orchestrator import (
    _filter_react_vite_generated_files,
    generate_project_async,
)
from backend.templates.react_vite_contract import (
    classify_react_vite_failure,
    restore_canonical_react_vite_contract,
    validate_react_vite_contract,
)


WORKSPACES = Path("workspaces")
CANONICAL_TEMPLATE = Path("templates") / "react-vite-ts"


def _copy_template(project_id: str, run_id: str) -> Path:
    target = WORKSPACES / project_id / run_id
    target.mkdir(parents=True, exist_ok=True)
    for item in CANONICAL_TEMPLATE.iterdir():
        dst = target / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)
    return target


def test_canonical_react_vite_template_validator_passes():
    project_id = f"test_contract_{uuid.uuid4().hex[:8]}"
    run_id = "run_template"
    _copy_template(project_id, run_id)

    report = validate_react_vite_contract(project_id, run_id)

    assert report.passed
    assert report.errors == []


def test_llm_output_cannot_overwrite_react_vite_contract_files():
    files = [
        GeneratedFile(path="package.json", content='{"scripts":{"build":"tsc && vite build"}}'),
        GeneratedFile(path="tsconfig.json", content='{"compilerOptions":{"noEmit":true}}'),
        GeneratedFile(path="tsconfig.app.json", content="{}"),
        GeneratedFile(path="tsconfig.node.json", content="{}"),
        GeneratedFile(path="vite.config.ts", content="export default {}"),
        GeneratedFile(path="index.html", content="<div>bad</div>"),
        GeneratedFile(path="src/main.tsx", content="throw new Error('bad')"),
        GeneratedFile(path="src/App.tsx", content="export default function App(){return <h1>Hello World</h1>}"),
    ]

    filtered = asyncio.run(_filter_react_vite_generated_files(files, "test-filter"))

    assert [f.path for f in filtered] == ["src/App.tsx"]


def test_ts6310_shaped_config_is_restored_in_one_deterministic_pass():
    project_id = f"test_ts6310_{uuid.uuid4().hex[:8]}"
    run_id = "run_bad_config"
    root = _copy_template(project_id, run_id)

    package_path = root / "package.json"
    package_text = package_path.read_text(encoding="utf-8").replace("tsc -b && vite build", "tsc && vite build")
    package_path.write_text(package_text, encoding="utf-8")
    tsconfig_path = root / "tsconfig.json"
    tsconfig_path.write_text(
        '{\n  "compilerOptions": { "noEmit": true },\n  "references": [\n'
        '    { "path": "./tsconfig.app.json" },\n'
        '    { "path": "./tsconfig.node.json" }\n  ]\n}\n',
        encoding="utf-8",
    )

    before = validate_react_vite_contract(project_id, run_id)
    restored = restore_canonical_react_vite_contract(project_id, run_id)
    after = validate_react_vite_contract(project_id, run_id)

    assert not before.passed
    assert any(err.startswith(RuntimeErrorCode.E_TS_REFERENCE_INVALID.value) for err in before.errors)
    assert "package.json" in restored
    assert "tsconfig.json" in restored
    assert after.passed
    assert after.errors == []


def test_invalid_tsconfig_build_failure_classifies_and_repairs_once():
    project_id = f"test_tsconfig_build_{uuid.uuid4().hex[:8]}"
    run_id = "run_invalid_config"
    root = _copy_template(project_id, run_id)
    subprocess.run(["npm.cmd", "install", "--no-progress"], cwd=root, check=True, capture_output=True, text=True)

    (root / "tsconfig.json").write_text('{ "files": [], "references": [', encoding="utf-8")
    failed = subprocess.run(["npm.cmd", "run", "build", "--no-progress"], cwd=root, capture_output=True, text=True)
    failure_type = classify_react_vite_failure(failed.stdout, failed.stderr)
    restored = restore_canonical_react_vite_contract(project_id, run_id)
    rebuilt = subprocess.run(["npm.cmd", "run", "build", "--no-progress"], cwd=root, capture_output=True, text=True)

    assert failed.returncode != 0
    assert failure_type == RuntimeErrorCode.E_TS_REFERENCE_INVALID.value
    assert "tsconfig.json" in restored
    assert rebuilt.returncode == 0


def test_repeated_hello_world_smoke_does_not_enter_repair_loops(monkeypatch):
    if os.getenv("RUN_REACT_VITE_SMOKE") != "1":
        return

    from backend.main import _register_builtin_skills
    from backend.sandbox.executor import _kill_process_tree, _runtime_registry
    import backend.orchestrator.project_orchestrator as orchestrator

    async def run_smoke():
        _register_builtin_skills()
        project_id = f"smoke_hello_{uuid.uuid4().hex[:8]}"
        terminal_lines = []
        states = []
        runtime_errors = []

        async def capture_terminal(text, type_str="info", project_id=None):
            terminal_lines.append(str(text))

        async def capture_state(state, project_id=None):
            states.append(str(state))

        async def capture_runtime_error(code, message, project_id=None, run_id=None, source="runtime"):
            runtime_errors.append({"code": str(code), "message": str(message), "source": source})

        def deterministic_complete(system_prompt, user_prompt, *args, **kwargs):
            return (
                "===FILE:package.json===\n"
                '{"scripts":{"build":"tsc && vite build"}}\n'
                "===END===\n"
                "===FILE:src/App.tsx===\n"
                "export default function App() { return <h1>Hello World</h1> }\n"
                "===END==="
            )

        monkeypatch.setattr(orchestrator, "complete", deterministic_complete)
        monkeypatch.setattr(orchestrator, "emit_terminal_line", capture_terminal)
        monkeypatch.setattr(orchestrator, "emit_agent_state", capture_state)
        monkeypatch.setattr(orchestrator, "emit_runtime_error", capture_runtime_error)

        results = []
        for _ in range(2):
            res = await generate_project_async(
                GenerateRequest(
                    project_id=project_id,
                    prompt="make hello world react vite",
                    auto_repair=True,
                    max_repair_attempts=1,
                    enabled_skills=["react-vite"],
                )
            )
            results.append(res)

        for entry in list(_runtime_registry.values()):
            _kill_process_tree(entry.popen, entry.project_id)
        _runtime_registry.clear()

        return results, terminal_lines, states, runtime_errors

    results, terminal_lines, states, runtime_errors = asyncio.run(run_smoke())

    assert all(res.success for res in results)
    joined = "\n".join(terminal_lines)
    assert "[Reflection]" not in joined
    assert "[Repair] Applied patch" not in joined
    assert "Skipping generated ecosystem contract overwrite: package.json" in joined
    assert not runtime_errors
    assert "repairing" not in states
    assert "validating" in states
    assert "verifying" in states
    assert "launching" in states


def test_runtime_state_contract_allows_expected_preview_lifecycle():
    assert can_transition("BUILDING", "STARTING_PREVIEW")
    assert can_transition("STARTING_PREVIEW", "PREVIEW_READY")
    assert can_transition("PREVIEW_READY", "VERIFYING")
    assert can_transition("VERIFYING", "COMPLETED")


def test_dependency_policy_classifies_undeclared_imports_without_installing():
    declared = {"react", "react-dom"}
    assert classify_dependency_import("react", declared) is None
    assert classify_dependency_import("lodash", declared) == RuntimeErrorCode.E_DEPENDENCY_MISSING
    assert DEPENDENCY_POLICY["mode"] == "declared_only"


def test_runtime_error_payload_is_structured_and_serializable():
    payload = error_payload(
        "RUNTIME_PORT_CONFLICT",
        "Port 5173 is occupied; using fallback port 5174",
        detail={"requestedPort": 5173, "selectedPort": 5174},
        severity="warning",
        recoverable=True,
        suggested_action="Use the selected fallback port or free the configured port.",
        project_id="phase2-taxonomy",
        source="runtime",
    )

    assert payload["code"] == "RUNTIME_PORT_CONFLICT"
    assert payload["message"]
    assert payload["detail"]["selectedPort"] == 5174
    assert payload["severity"] == "warning"
    assert payload["recoverable"] is True
    assert isinstance(payload["timestamp"], int)
    assert payload["suggestedAction"]


def test_no_legacy_react_vite_template_configs_remain():
    legacy = Path("backend") / "templates" / "vite-react-ts"
    config_files = list(legacy.glob("**/*")) if legacy.exists() else []
    assert [p for p in config_files if p.is_file() and p.suffix in {".json", ".ts", ".tsx", ".css", ".html", ".js"}] == []
