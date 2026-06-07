import asyncio
import unittest

from backend.orchestrator.artifact_contracts import (
    ArtifactContractRegistry,
    discover_artifact_descriptors,
    discover_artifacts,
)
from backend.orchestrator.generation.orchestrator import format_artifact_contract_prompt
from backend.orchestrator.artifact_taxonomy import ArtifactCategory
from backend.orchestrator.planning_engine import PlanningEngine
from backend.orchestrator.task_graph import ExecutionTask, TaskExecutor, TaskGraph


class TestArtifactContracts(unittest.TestCase):
    def test_artifact_contract_prompt_includes_requires_and_produces(self):
        task = ExecutionTask(
            id="marketplace_store",
            title="Create marketplace state store",
            description="",
            requires_artifacts=["Product", "CartItem", "Order"],
            produces_artifacts=["useMarketplaceStore"],
        )

        prompt = format_artifact_contract_prompt(task)

        self.assertIn("=== ARTIFACT CONTRACT ===", prompt)
        self.assertIn("This task REQUIRES artifacts:", prompt)
        self.assertIn("- Product", prompt)
        self.assertIn("- CartItem", prompt)
        self.assertIn("- Order", prompt)
        self.assertIn("This task MUST PRODUCE artifacts:", prompt)
        self.assertIn("- useMarketplaceStore", prompt)
        self.assertIn("export const useMarketplaceStore = ...", prompt)
        self.assertIn("export function useMarketplaceStore(...) { ... }", prompt)
        self.assertIn("exported exactly by name", prompt)

    def test_artifact_contract_prompt_is_empty_without_contract(self):
        task = ExecutionTask(id="hello_world", title="Render Hello World", description="")

        self.assertEqual(format_artifact_contract_prompt(task), "")

    def test_artifact_contract_prompt_mentions_marketplace_page_exact_export(self):
        task = ExecutionTask(
            id="marketplace_components",
            title="Build marketplace UI components",
            description="",
            produces_artifacts=["MarketplacePage"],
        )

        prompt = format_artifact_contract_prompt(task)

        self.assertIn("- MarketplacePage", prompt)
        self.assertIn("export function MarketplacePage() { ... }", prompt)
        self.assertIn("export default function MarketplacePage() { ... }", prompt)
        self.assertIn("Do not rename produced artifacts.", prompt)

    def test_typescript_artifact_discovery_finds_exports_and_hook_alias(self):
        content = """
        export interface Product { id: string }
        export type CartItem = Product & { quantity: number }
        export enum OrderStatus { Draft }
        export const useInventoryStore = () => ({})
        export function MarketplacePage() { return null }
        export default function CrudPage() { return null }
        """

        artifacts = discover_artifacts("src/components/Example.tsx", content)

        self.assertIn("Product", artifacts)
        self.assertIn("CartItem", artifacts)
        self.assertIn("OrderStatus", artifacts)
        self.assertIn("useInventoryStore", artifacts)
        self.assertIn("InventoryStore", artifacts)
        self.assertIn("MarketplacePage", artifacts)
        self.assertIn("CrudPage", artifacts)

    def test_artifact_taxonomy_classifies_discovered_exports(self):
        content = """
        export interface Product { id: string }
        export const useMarketplaceStore = () => ({})
        export default function ProductCatalog() { return null }
        export function MarketplacePage() { return null }
        """

        descriptors = {
            descriptor.name: descriptor.artifact_category
            for descriptor in discover_artifact_descriptors("src/components/MarketplacePage.tsx", content)
        }

        self.assertEqual(descriptors["Product"], ArtifactCategory.TYPE)
        self.assertEqual(descriptors["useMarketplaceStore"], ArtifactCategory.STORE)
        self.assertEqual(descriptors["MarketplaceStore"], ArtifactCategory.STORE)
        self.assertEqual(descriptors["ProductCatalog"], ArtifactCategory.COMPONENT)
        self.assertEqual(descriptors["MarketplacePage"], ArtifactCategory.PAGE)

    def test_app_tsx_root_is_classified_as_app_entry(self):
        descriptors = {
            descriptor.name: descriptor.artifact_category
            for descriptor in discover_artifact_descriptors("src/App.tsx", "export default function App() { return null }")
        }

        self.assertEqual(descriptors["App"], ArtifactCategory.APP_ENTRY)

    def test_registry_stores_artifact_category_and_logs_taxonomy(self):
        registry = ArtifactContractRegistry()
        task = ExecutionTask(
            id="marketplace_components",
            title="Build marketplace UI components",
            description="",
            produces_artifacts=["MarketplacePage"],
        )

        with self.assertLogs("backend.orchestrator.artifact_contracts", level="INFO") as captured:
            result = registry.register_discovered_files(
                task,
                {"src/components/MarketplacePage.tsx": "export function MarketplacePage() { return null }"},
            )

        self.assertTrue(result.passed)
        self.assertEqual(registry.produced_artifacts["MarketplacePage"].artifact_category, ArtifactCategory.PAGE)
        self.assertIn("[ArtifactTaxonomy] category=PAGE artifact=MarketplacePage", "\n".join(captured.output))

    def test_marketplace_store_blocks_when_product_is_missing(self):
        registry = ArtifactContractRegistry()
        task = ExecutionTask(
            id="marketplace_store",
            title="Create marketplace state store",
            description="",
            requires_artifacts=["Product", "CartItem", "Order"],
        )

        result = registry.validate_requirements(task)

        self.assertFalse(result.passed)
        self.assertEqual(result.missing_artifacts, ["Product", "CartItem", "Order"])

    def test_inventory_components_blocks_when_inventory_store_is_missing(self):
        registry = ArtifactContractRegistry()
        task = ExecutionTask(
            id="inventory_components",
            title="Build inventory screens",
            description="",
            requires_artifacts=["InventoryStore"],
        )

        result = registry.validate_requirements(task)

        self.assertFalse(result.passed)
        self.assertEqual(result.missing_artifacts, ["InventoryStore"])

    def test_crud_compose_blocks_when_crud_page_is_missing(self):
        registry = ArtifactContractRegistry()
        task = ExecutionTask(
            id="compose_crud_app",
            title="Compose CRUD app shell",
            description="",
            requires_artifacts=["CrudPage"],
        )

        result = registry.validate_requirements(task)

        self.assertFalse(result.passed)
        self.assertEqual(result.missing_artifacts, ["CrudPage"])

    def test_task_executor_fails_fast_before_running_missing_requirement_task(self):
        registry = ArtifactContractRegistry()
        graph = TaskGraph()
        task = ExecutionTask(
            id="marketplace_store",
            title="Create marketplace state store",
            description="",
            requires_artifacts=["Product"],
        )
        graph.add_task(task)
        ran_tasks = []

        async def callback(current_task):
            ran_tasks.append(current_task.id)
            return True

        success = asyncio.run(TaskExecutor(graph, artifact_registry=registry).execute_all(callback))

        self.assertFalse(success)
        self.assertEqual(ran_tasks, [])
        self.assertIn("missing artifacts", task.error_msg)

    def test_declared_production_must_be_discovered(self):
        registry = ArtifactContractRegistry()
        task = ExecutionTask(
            id="types_and_seed_data",
            title="Define marketplace data model",
            description="",
            produces_artifacts=["Product"],
        )

        result = registry.register_discovered_files(
            task,
            {"src/types.ts": "export interface Customer { id: string }"},
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.missing_artifacts, ["Product"])
        self.assertNotIn("Product", registry.produced_artifacts)

    def test_task_without_artifact_contract_remains_backward_compatible(self):
        graph = TaskGraph()
        graph.add_task(ExecutionTask(id="hello_world", title="Render Hello World", description=""))
        ran_tasks = []

        async def callback(current_task):
            ran_tasks.append(current_task.id)
            return True

        success = asyncio.run(TaskExecutor(graph, artifact_registry=ArtifactContractRegistry()).execute_all(callback))

        self.assertTrue(success)
        self.assertEqual(ran_tasks, ["hello_world"])

    def test_contract_templates_are_threaded_into_deterministic_tasks(self):
        graph = PlanningEngine._deterministic_plan("buat marketplace modern")

        self.assertEqual(graph.tasks["types_and_seed_data"].produces_artifacts, ["Product", "CartItem", "Order"])
        self.assertEqual(graph.tasks["marketplace_store"].requires_artifacts, ["Product", "CartItem", "Order"])
        self.assertEqual(graph.tasks["marketplace_store"].produces_artifacts, ["useMarketplaceStore"])
        self.assertEqual(graph.tasks["marketplace_components"].requires_artifacts, ["useMarketplaceStore", "Product"])
        self.assertEqual(graph.tasks["marketplace_components"].produces_artifacts, ["MarketplacePage"])
        self.assertEqual(graph.tasks["compose_marketplace_app"].requires_artifacts, ["MarketplacePage"])


if __name__ == "__main__":
    unittest.main()
