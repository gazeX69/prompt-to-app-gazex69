import shutil
import unittest
from pathlib import Path
from uuid import uuid4

from backend.memory.workspace_awareness import WorkspaceAwareness, WORKSPACE_AWARENESS_RELATIVE_PATH


class TestWorkspaceAwareness(unittest.TestCase):
    def setUp(self):
        self.project_id = f"wa_{uuid4().hex[:8]}"
        self.run_id = "run_20260604_000000_test"
        self.workspace = Path("workspaces") / self.project_id
        self.run_dir = self.workspace / self.run_id
        (self.run_dir / "src/components").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "src/hooks").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "src/services").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "package.json").write_text(
            """{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "typescript": "^5.0.0",
    "tailwindcss": "^3.4.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  }
}
""",
            encoding="utf-8",
        )
        (self.run_dir / "src/main.tsx").write_text(
            "import App from './App'\nimport './index.css'\n<App />\n",
            encoding="utf-8",
        )
        (self.run_dir / "src/App.tsx").write_text(
            "import { ProductCatalog } from './components/ProductCatalog'\nexport default function App(){ return <ProductCatalog /> }\n",
            encoding="utf-8",
        )
        (self.run_dir / "src/components/ProductCatalog.tsx").write_text(
            "import { useProductStore } from '../hooks/useProductStore'\nexport function ProductCatalog(){ const products = useProductStore(s => s.products); return <div>{products.length}</div> }\n",
            encoding="utf-8",
        )
        (self.run_dir / "src/hooks/useProductStore.ts").write_text(
            "import { create } from 'zustand'\nimport { fetchProducts } from '../services/productApi'\nexport const useProductStore = create(() => ({ products: [], fetchProducts }))\n",
            encoding="utf-8",
        )
        (self.run_dir / "src/services/productApi.ts").write_text(
            "import axios from 'axios'\nexport const fetchProducts = () => axios.get('/api/products')\n",
            encoding="utf-8",
        )
        (self.run_dir / "src/index.css").write_text("@tailwind base;\n", encoding="utf-8")

    def tearDown(self):
        if self.workspace.exists():
            shutil.rmtree(self.workspace)

    def test_workspace_awareness_level_1_to_6_chain(self):
        awareness = WorkspaceAwareness.scan(self.project_id, run_id=self.run_id, prompt="tambahkan wishlist produk")
        state_path = self.workspace / WORKSPACE_AWARENESS_RELATIVE_PATH
        self.assertTrue(state_path.exists())

        maturity = awareness["maturity"]
        self.assertTrue(maturity["level_1_file_awareness"])
        self.assertTrue(maturity["level_2_structure_awareness"])
        self.assertTrue(maturity["level_3_dependency_awareness"])
        self.assertTrue(maturity["level_4_pattern_awareness"])
        self.assertTrue(maturity["level_5_impact_awareness"])
        self.assertTrue(maturity["level_6_architecture_explanation"])

        self.assertIn("react", awareness["stack"]["stack"])
        self.assertIn("vite", awareness["stack"]["stack"])
        self.assertIn("src/components", awareness["structure"]["directories"])
        self.assertIn("zustand", awareness["patterns"]["state_management"])
        self.assertIn("axios", awareness["patterns"]["api_layer"])
        self.assertIn("src/components/ProductCatalog.tsx", awareness["dependencies"]["reverse_graph"]["src/hooks/useProductStore.ts"])
        self.assertIn("UI", awareness["architecture"]["flow"])
        self.assertIn("wishlist", awareness["impact_analysis"]["prompt_domains"])

    def test_workspace_awareness_context_and_summary(self):
        context = WorkspaceAwareness.build_context(self.project_id, run_id=self.run_id, prompt="ubah product")
        self.assertIn("WORKSPACE AWARENESS", context)
        self.assertIn("Stack:", context)

        summary = WorkspaceAwareness.describe(self.project_id)
        self.assertIn("summary", summary)
        self.assertGreater(summary["confidence"], 0.5)


if __name__ == "__main__":
    unittest.main()
