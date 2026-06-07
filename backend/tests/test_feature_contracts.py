import unittest

from backend.validation.feature_contracts import (
    BrowserAction,
    ContractCapability,
    FeatureContractContext,
    FeatureContractFailure,
    FeatureContractRegistry,
    FeatureContractResult,
    FeatureContractRunner,
    FeatureDescriptor,
    FeatureManifest,
    PlaywrightBrowserDriver,
    build_action_plan,
    default_registry,
    infer_capability,
    run_feature_contracts,
)


class TestFeatureContracts(unittest.IsolatedAsyncioTestCase):
    async def test_empty_registry_succeeds(self):
        context = FeatureContractContext(
            project_id="feature_contract_smoke",
            run_id="run_feature_contract_smoke",
            preview_url="http://127.0.0.1:3000",
            prompt="buat hello world",
            app_type="hello_world",
            domain="general",
        )

        result = await run_feature_contracts(context)

        self.assertTrue(result.success)
        self.assertEqual(result.contracts_executed, [])
        self.assertEqual(result.selected_contracts, [contract.contract_id for contract in default_registry.list_descriptors()])
        self.assertEqual(len(result.action_plans), len(default_registry.list_descriptors()))
        self.assertEqual(result.failures, [])
        self.assertGreaterEqual(result.duration_ms, 0)
        self.assertEqual(result.to_dict()["success"], True)

    async def test_registered_contract_failure_is_reported(self):
        registry = FeatureContractRegistry()

        async def failing_contract(_context):
            return FeatureContractResult(
                success=False,
                contracts_executed=["future_contract"],
                failures=[
                    FeatureContractFailure(
                        contract_id="future_contract",
                        message="Future behavior failed",
                    )
                ],
            )

        registry.register("future_contract", ContractCapability.CREATE_ENTITY, failing_contract)
        context = FeatureContractContext(
            project_id="feature_contract_smoke",
            run_id="run_feature_contract_smoke",
            preview_url="http://127.0.0.1:3000",
            prompt="future feature",
            feature_manifest=FeatureManifest(
                project_id="feature_contract_smoke",
                run_id="run_feature_contract_smoke",
                features=[FeatureDescriptor("create_entity", "create", 0.9, "test")],
            ),
        )

        result = await FeatureContractRunner(registry=registry).run(context)

        self.assertFalse(result.success)
        self.assertEqual(result.contracts_executed, ["future_contract"])
        self.assertEqual(result.selected_contracts, ["future_contract"])
        self.assertEqual(result.action_plans[0].contract_id, "future_contract")
        self.assertEqual(result.failures[0].contract_id, "future_contract")

    async def test_manifest_selects_generic_contracts_without_app_type_mapping(self):
        manifest = FeatureManifest(
            project_id="feature_contract_smoke",
            run_id="run_feature_contract_smoke",
            app_type="anything",
            features=[
                FeatureDescriptor("create_task", "create", 0.9, "test"),
                FeatureDescriptor("edit_task", "update", 0.9, "test"),
                FeatureDescriptor("delete_task", "delete", 0.9, "test"),
            ],
        )

        selected = default_registry.select_contracts(manifest)
        result = await FeatureContractRunner(registry=default_registry).run(
            FeatureContractContext(
                project_id="feature_contract_smoke",
                run_id="run_feature_contract_smoke",
                preview_url="http://127.0.0.1:3000",
                prompt="future feature",
                feature_manifest=manifest,
            )
        )

        self.assertEqual([contract.contract_id for contract in selected], ["entity_create", "entity_update", "entity_delete"])
        self.assertEqual(result.selected_contracts, ["entity_create", "entity_update", "entity_delete"])
        self.assertEqual([plan.contract_id for plan in result.action_plans], ["entity_create", "entity_update", "entity_delete"])
        self.assertEqual(
            [action.action_type for action in result.action_plans[1].actions],
            ["locate_entity", "open_editor", "modify_value", "save_changes", "verify_change"],
        )
        self.assertEqual(result.contracts_executed, [])
        self.assertTrue(result.success)

    async def test_feature_action_maps_to_capability_not_app_type(self):
        self.assertEqual(infer_capability(FeatureDescriptor("update_product")), ContractCapability.UPDATE_ENTITY)
        self.assertEqual(infer_capability(FeatureDescriptor("edit_profile")), ContractCapability.UPDATE_ENTITY)
        self.assertEqual(infer_capability(FeatureDescriptor("create_user")), ContractCapability.CREATE_ENTITY)

    async def test_contract_descriptor_builds_browser_action_plan(self):
        descriptor = default_registry.get_descriptor("entity_update")

        plan = build_action_plan(descriptor)

        self.assertEqual(plan.contract_id, "entity_update")
        self.assertEqual(plan.capability, ContractCapability.UPDATE_ENTITY)
        self.assertEqual(
            [action.action_type for action in plan.actions],
            ["locate_entity", "open_editor", "modify_value", "save_changes", "verify_change"],
        )
        self.assertEqual(plan.to_dict()["actions"][0]["action_type"], "locate_entity")

    async def test_playwright_driver_adapter_is_non_executing_foundation(self):
        driver = PlaywrightBrowserDriver()
        session = await driver.open("http://127.0.0.1:3000")

        result = await driver.run_action(session, BrowserAction("locate_entity"))

        self.assertFalse(result.success)
        self.assertIn("not implemented", result.message)
        self.assertEqual(result.detail["preview_url"], "http://127.0.0.1:3000")


if __name__ == "__main__":
    unittest.main()
