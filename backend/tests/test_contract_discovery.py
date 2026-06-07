import unittest

from backend.brain.contract_discovery import discover_contract
from backend.brain.domain_contract_registry import load_contract
from backend.brain.plan_signature import build_plan_signature


class TestContractDiscovery(unittest.TestCase):
    def test_discovery_matches_registered_contracts(self):
        cases = [
            ("buat marketplace modern", "marketplace"),
            ("buat sistem inventory", "inventory"),
            ("buat dashboard admin", "dashboard"),
            ("buat CRUD produk", "crud_app"),
        ]

        for prompt, expected_app_type in cases:
            with self.subTest(prompt=prompt):
                result = discover_contract(prompt)
                self.assertIsNotNone(result.contract)
                self.assertEqual(result.contract["app_type"], expected_app_type)
                self.assertGreater(result.confidence, 0)
                self.assertGreater(len(result.matched_keywords), 0)

    def test_plan_signature_uses_contract_registry_fields(self):
        contract = load_contract("marketplace")
        signature = build_plan_signature("buat marketplace modern")

        self.assertEqual(signature.domain, contract["domain"])
        self.assertEqual(signature.app_type, contract["app_type"])
        self.assertEqual(signature.complexity.value, contract["complexity_default"].lower())
        self.assertEqual(signature.feature_keywords, contract["feature_keywords"])
        self.assertEqual(signature.required_capabilities, contract["required_capabilities"])

    def test_unmatched_domain_stays_unknown(self):
        signature = build_plan_signature("buat aplikasi web portal perpustakaan sekolah")

        self.assertEqual(signature.domain, "UNKNOWN_DOMAIN")
        self.assertEqual(signature.app_type, "unknown_domain")


if __name__ == "__main__":
    unittest.main()
