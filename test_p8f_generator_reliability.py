import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.agent.tools as tools
from backend.runtime_contract import RuntimeErrorCode
from backend.templates.react_vite_contract import validate_react_vite_contract


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_minimal_react_vite_project(root: Path, app_source: str) -> None:
    _write(
        root / "package.json",
        json.dumps(
            {
                "scripts": {
                    "dev": "vite",
                    "build": "tsc -b && vite build",
                    "preview": "vite preview",
                },
                "dependencies": {
                    "react": "^18.3.1",
                    "react-dom": "^18.3.1",
                },
                "devDependencies": {
                    "@types/node": "^22.10.2",
                    "@types/react": "^18.3.18",
                    "@types/react-dom": "^18.3.5",
                    "@vitejs/plugin-react": "^4.3.4",
                    "typescript": "^5.7.2",
                    "vite": "^5.4.11",
                },
            }
        ),
    )
    _write(root / "tsconfig.json", json.dumps({"files": [], "references": [{"path": "./tsconfig.app.json"}, {"path": "./tsconfig.node.json"}]}))
    _write(
        root / "tsconfig.app.json",
        json.dumps({"compilerOptions": {"moduleResolution": "bundler", "jsx": "react-jsx", "noEmit": True}, "include": ["src"]}),
    )
    _write(
        root / "tsconfig.node.json",
        json.dumps({"compilerOptions": {"moduleResolution": "bundler", "noEmit": True, "types": ["node"]}, "include": ["vite.config.ts"]}),
    )
    _write(root / "vite.config.ts", "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\nexport default defineConfig({ plugins: [react()] });\n")
    _write(root / "index.html", '<div id="root"></div><script type="module" src="/src/main.tsx"></script>')
    _write(root / "src/main.tsx", "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App';\ncreateRoot(document.getElementById('root')!).render(<App />);\n")
    _write(root / "src/index.css", "body { margin: 0; }\n")
    _write(root / "src/App.tsx", app_source)


class P8FGeneratorReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.tempdir.name) / "workspaces"
        self.project_id = "p8f_contract"
        self.run_id = "run_contract"
        self.project_root = self.workspace_root / self.project_id / self.run_id
        self.patch = patch.object(tools, "WORKSPACE_ROOT", self.workspace_root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tempdir.cleanup()

    def test_react_vite_contract_accepts_declared_imports(self):
        _write_minimal_react_vite_project(
            self.project_root,
            "import { useState } from 'react';\nexport default function App(){ const [count] = useState(0); return <button>{count}</button>; }\n",
        )

        report = validate_react_vite_contract(self.project_id, self.run_id)

        self.assertTrue(report.passed, report.summary())

    def test_react_vite_contract_rejects_undeclared_external_import_before_success(self):
        _write_minimal_react_vite_project(
            self.project_root,
            "import { BrowserRouter } from 'react-router-dom';\nexport default function App(){ return <BrowserRouter />; }\n",
        )

        report = validate_react_vite_contract(self.project_id, self.run_id)

        self.assertFalse(report.passed)
        self.assertIn(
            f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:react-router-dom:src/App.tsx",
            report.errors,
        )

    def test_react_vite_contract_rejects_side_effect_and_dynamic_undeclared_imports(self):
        _write_minimal_react_vite_project(
            self.project_root,
            "import 'lucide-react';\nvoid import('date-fns');\nexport default function App(){ return <main>Hi</main>; }\n",
        )

        report = validate_react_vite_contract(self.project_id, self.run_id)

        self.assertFalse(report.passed)
        self.assertIn(f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:lucide-react:src/App.tsx", report.errors)
        self.assertIn(f"{RuntimeErrorCode.E_DEPENDENCY_MISSING.value}:date-fns:src/App.tsx", report.errors)


if __name__ == "__main__":
    unittest.main()
