import json
import shutil
import uuid
from pathlib import Path

from backend.core.dependency_resolution import (
    apply_native_dependency_repair,
    resolve_dependency_health,
)
from backend.runtime_contract import RuntimeErrorCode
from backend.templates.react_vite_contract import validate_react_vite_contract


WORKSPACES = Path("workspaces")
CANONICAL_TEMPLATE = Path("templates") / "react-vite-ts"


def _copy_template(project_id: str, run_id: str = "run_test") -> Path:
    target = WORKSPACES / project_id / run_id
    target.mkdir(parents=True, exist_ok=True)
    for item in CANONICAL_TEMPLATE.iterdir():
        dst = target / item.name
        if item.is_dir():
            shutil.copytree(item, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dst)
    return target


def _package_json(project_path: Path) -> dict:
    return json.loads((project_path / "package.json").read_text(encoding="utf-8"))


def _write_package_json(project_path: Path, data: dict) -> None:
    (project_path / "package.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_uuid_import_is_dependency_failure_not_contract_failure():
    project_id = f"dep_uuid_{uuid.uuid4().hex[:8]}"
    run_id = "run_test"
    project_path = _copy_template(project_id, run_id)
    data_path = project_path / "src" / "lib" / "data.ts"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        "import { v4 as uuidv4 } from 'uuid'\n\nexport const id = uuidv4()\n",
        encoding="utf-8",
    )

    dependency_report = resolve_dependency_health(project_id, run_id)
    contract_report = validate_react_vite_contract(project_id, run_id)

    assert any(item["package"] == "uuid" for item in dependency_report["missing_dependencies"])
    assert dependency_report["status"] == "dependency_resolution_failure"
    assert contract_report.passed
    assert not any("E_DEPENDENCY_MISSING:uuid" in error for error in contract_report.errors)
    assert any("E_DEPENDENCY_MISSING:uuid" in warning for warning in contract_report.warnings)


def test_missing_react_is_contract_failure():
    project_id = f"dep_react_{uuid.uuid4().hex[:8]}"
    run_id = "run_test"
    project_path = _copy_template(project_id, run_id)
    package_data = _package_json(project_path)
    package_data["dependencies"].pop("react", None)
    _write_package_json(project_path, package_data)

    contract_report = validate_react_vite_contract(project_id, run_id)
    dependency_report = resolve_dependency_health(project_id, run_id)

    assert not contract_report.passed
    assert f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:react" in ";".join(contract_report.errors)
    assert any(item["package"] == "react" for item in dependency_report["missing_dependencies"])


def test_missing_vite_is_contract_failure():
    project_id = f"dep_vite_{uuid.uuid4().hex[:8]}"
    run_id = "run_test"
    project_path = _copy_template(project_id, run_id)
    package_data = _package_json(project_path)
    package_data["devDependencies"].pop("vite", None)
    _write_package_json(project_path, package_data)

    contract_report = validate_react_vite_contract(project_id, run_id)
    dependency_report = resolve_dependency_health(project_id, run_id)

    assert not contract_report.passed
    assert f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:vite" in ";".join(contract_report.errors)
    assert any(item["package"] == "vite" for item in dependency_report["missing_dependencies"])


def test_uuid_native_repair_resolves_dependency_issue():
    project_id = f"dep_repair_{uuid.uuid4().hex[:8]}"
    run_id = "run_test"
    project_path = _copy_template(project_id, run_id)
    data_path = project_path / "src" / "lib" / "data.ts"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        "import { v4 as uuidv4 } from 'uuid'\n\nexport const id = uuidv4()\n",
        encoding="utf-8",
    )

    before = resolve_dependency_health(project_id, run_id)
    after = apply_native_dependency_repair(project_id, run_id, report=before)
    repaired_text = data_path.read_text(encoding="utf-8")

    assert any(item["package"] == "uuid" for item in before["missing_dependencies"])
    assert "from 'uuid'" not in repaired_text
    assert "crypto.randomUUID()" in repaired_text
    assert not any(item["package"] == "uuid" for item in after["missing_dependencies"])
    assert after["status"] == "healthy"
