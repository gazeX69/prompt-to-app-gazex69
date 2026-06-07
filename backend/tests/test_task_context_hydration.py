import tempfile
import unittest
from pathlib import Path

from backend.orchestrator.context_hydrator import (
    ContextHydrator,
    detect_schema_drift,
    format_existing_code_reuse_context,
)
from backend.orchestrator.task_graph import ExecutionTask, TaskGraph, TaskStatus
from backend.reflection.repair_loop import RepairAnalyzer


class TestTaskContextHydration(unittest.TestCase):
    def test_required_artifacts_include_existing_producer_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            types_path = root / "sim" / "types.ts"
            store_path = root / "sim" / "useMarketplaceStore.ts"
            types_path.parent.mkdir(parents=True, exist_ok=True)
            types_path.write_text(
                """
export interface Product {
  id: string;
  name: string;
  price: number;
  description: string;
  category: string;
  image: string;
  stock: number;
}
""",
                encoding="utf-8",
            )
            store_path.write_text(
                """
export const useMarketplaceStore = () => ({
  products: [] as Product[],
});
""",
                encoding="utf-8",
            )

            graph = TaskGraph()
            types_task = ExecutionTask(
                id="types_and_seed_data",
                title="Define marketplace data model",
                description="",
                produces_artifacts=["Product"],
                status=TaskStatus.COMPLETED,
                proposed_artifacts={"src/types.ts": str(types_path)},
            )
            store_task = ExecutionTask(
                id="marketplace_store",
                title="Create marketplace state store",
                description="",
                dependencies=["types_and_seed_data"],
                requires_artifacts=["Product"],
                produces_artifacts=["useMarketplaceStore"],
                status=TaskStatus.COMPLETED,
                proposed_artifacts={"src/hooks/useMarketplaceStore.ts": str(store_path)},
            )
            component_task = ExecutionTask(
                id="marketplace_components",
                title="Build marketplace UI components",
                description="",
                dependencies=["marketplace_store"],
                requires_artifacts=["Product", "useMarketplaceStore"],
                allowed_write_paths=["src/components/MarketplacePage.tsx"],
            )
            graph.add_task(types_task)
            graph.add_task(store_task)
            graph.add_task(component_task)

            bundle = ContextHydrator(str(root), "sess_test", graph).hydrate_context(component_task)
            reuse_context = format_existing_code_reuse_context(bundle)

            self.assertIn("Product", bundle.existing_artifact_context)
            self.assertIn("useMarketplaceStore", bundle.existing_artifact_context)
            self.assertIn("Current Product definition:", reuse_context)
            self.assertIn("category: string", reuse_context)
            self.assertIn("Current useMarketplaceStore definition:", reuse_context)
            self.assertIn("USE EXISTING TYPES.", reuse_context)
            self.assertIn("Do not create a second schema", reuse_context)

    def test_schema_drift_detects_product_object_missing_required_fields(self):
        files = {
            "src/types.ts": """
export interface Product {
  id: string;
  name: string;
  price: number;
  description: string;
  category: string;
  image: string;
  stock: number;
}
""",
            "src/data/seedProducts.ts": """
export const initialProducts: Product[] = [
  {
    id: '1',
    name: 'Desk',
    price: 120,
    description: 'Wood desk'
  }
];
""",
        }

        findings = detect_schema_drift(files)

        self.assertEqual(len(findings), 1)
        self.assertIn("Schema Drift Detected", findings[0])
        self.assertIn("category", findings[0])
        self.assertIn("image", findings[0])
        self.assertIn("stock", findings[0])

    def test_schema_drift_allows_complete_product_object(self):
        files = {
            "src/types.ts": """
export interface Product {
  id: string;
  name: string;
  price: number;
  description: string;
  category: string;
  image: string;
  stock: number;
}
""",
            "src/data/seedProducts.ts": """
export const initialProducts: Product[] = [
  {
    id: '1',
    name: 'Desk',
    price: 120,
    description: 'Wood desk',
    category: 'Furniture',
    image: '/desk.png',
    stock: 4
  }
];
""",
        }

        self.assertEqual(detect_schema_drift(files), [])

    def test_reflection_classifies_missing_properties_as_schema_drift(self):
        stderr = "TS2741: Property 'category' is missing in type '{ id: string; name: string; }' but required in type 'Product'."

        self.assertEqual(RepairAnalyzer.classify_failure(stderr, ""), "schema_drift_missing_properties")


if __name__ == "__main__":
    unittest.main()
