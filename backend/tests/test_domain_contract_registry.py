import logging
import unittest

from backend.brain.domain_contract_registry import (
    clear_contract_cache,
    get_contract_capabilities,
    get_contract_decisions,
    get_contract_features,
    get_contract_mvp_features,
    get_contract_validation_rules,
    load_contract,
)
from backend.brain.domain_contracts import get_broad_match_type, get_contract


class TestDomainContractRegistry(unittest.TestCase):
    def setUp(self):
        clear_contract_cache()

    def test_load_marketplace_contract_supports_required_sections(self):
        contract = load_contract("marketplace")

        self.assertEqual(contract["app_type"], "marketplace")
        self.assertEqual(contract["contract_version"], "v1")
        self.assertIn("marketplace", contract["keywords"])
        self.assertIn("produk", contract["features"])
        self.assertIn("product_catalog", contract["capabilities"])
        self.assertIn("payment", contract["decisions"])
        self.assertIn("Cart", contract["mvp_features"])
        self.assertEqual(contract["validation_rules"]["min_interactive"], 5)

    def test_registry_helper_accessors_return_normalized_fields(self):
        self.assertIn("stok", get_contract_features("inventory"))
        self.assertIn("data_persistence", get_contract_capabilities("crud_app"))
        self.assertIn("entity", get_contract_decisions("crud_app"))
        self.assertIn("Low stock indicator", get_contract_mvp_features("inventory"))
        self.assertIn("expected_terms", get_contract_validation_rules("marketplace"))

    def test_compatibility_package_exports_use_registry(self):
        contract = get_contract("marketplace")

        self.assertIsNotNone(contract)
        self.assertEqual(contract["contract_version"], "v1")
        self.assertEqual(get_broad_match_type("buat marketplace"), "marketplace")

    def test_contract_registry_emits_trace_logs(self):
        logger_name = "backend.brain.domain_contract_registry"
        with self.assertLogs(logger_name, level=logging.INFO) as captured:
            load_contract("marketplace")

        logs = "\n".join(captured.output)
        self.assertIn("[ContractRegistry] Kontrak yang dimuat: marketplace", logs)
        self.assertIn("[ContractRegistry] Versi kontrak: v1", logs)
        self.assertIn("[ContractRegistry] Fitur: produk, keranjang, pembayaran", logs)


if __name__ == "__main__":
    unittest.main()
