import unittest
from backend.brain.plan_signature import (
    _levenshtein_distance,
    _get_broad_match_type,
    build_plan_signature,
)
from backend.brain.scope_analyzer import analyze_scope
from backend.brain.decision_engine import decide_preflight
from backend.brain.schemas import BrainDecision, ComplexityLevel


class TestSkepticAI(unittest.TestCase):
    def test_levenshtein_distance(self):
        # Exact match
        self.assertEqual(_levenshtein_distance("marketplace", "marketplace"), 0)
        # Insertion
        self.assertEqual(_levenshtein_distance("market", "marketp"), 1)
        # Deletion
        self.assertEqual(_levenshtein_distance("marketplace", "marketpce"), 2)
        # Substitution
        self.assertEqual(_levenshtein_distance("cat", "cut"), 1)

    def test_broad_match_type_typos(self):
        # Typos in marketplace
        self.assertEqual(_get_broad_match_type("buat marketpce"), "marketplace")
        self.assertEqual(_get_broad_match_type("toko online"), "marketplace")
        self.assertEqual(_get_broad_match_type("olshop murah"), "marketplace")
        
        # Typos in ecommerce
        self.assertEqual(_get_broad_match_type("build e-comerce"), "marketplace")
        self.assertEqual(_get_broad_match_type("ekomere"), "marketplace")

        # Typos/Variations in saas
        self.assertEqual(_get_broad_match_type("bikin sas"), "saas")
        self.assertEqual(_get_broad_match_type("saas dashboard"), "saas")

        # Typos in lms/lsm
        self.assertEqual(_get_broad_match_type("buat lsm"), "lms")

        # No match for simple apps
        self.assertIsNone(_get_broad_match_type("buat todo app"))
        self.assertIsNone(_get_broad_match_type("halo dunia"))

    def test_plan_signature_classification(self):
        # Typo should still result in marketplace and HIGH complexity
        sig = build_plan_signature("buat marketpce")
        self.assertEqual(sig.app_type, "marketplace")
        self.assertEqual(sig.complexity, ComplexityLevel.HIGH)

        # Simple app should be LOW complexity
        sig_todo = build_plan_signature("buat todo app")
        self.assertEqual(sig_todo.app_type, "todo")
        self.assertEqual(sig_todo.complexity, ComplexityLevel.LOW)

    def test_short_vague_prompt_heuristic(self):
        # Extremely short general app prompt
        sig_vague = build_plan_signature("buat aplikasi")
        self.assertEqual(sig_vague.app_type, "crud_app")
        self.assertEqual(sig_vague.complexity, ComplexityLevel.HIGH)

        # Long specific app prompt (should not trigger vague heuristic)
        sig_specific = build_plan_signature("buat aplikasi web portal untuk reservasi peminjaman buku perpustakaan sekolah")
        self.assertEqual(sig_specific.app_type, "booking")
        self.assertEqual(sig_specific.complexity, ComplexityLevel.HIGH)

    def test_decide_preflight_outcomes(self):
        # Typo prompt preflight decision
        sig = build_plan_signature("buat marketpce")
        scope = analyze_scope("buat marketpce", sig)
        res = decide_preflight("buat marketpce", sig, scope, [])
        self.assertEqual(res.decision, BrainDecision.ASK_USER_BEFORE_GENERATE)
        self.assertTrue(res.planning_required)
        self.assertGreater(len(res.scope_analysis.missing_decisions), 0)

        # Vague prompt preflight decision
        sig_vague = build_plan_signature("buat aplikasi")
        scope_vague = analyze_scope("buat aplikasi", sig_vague)
        res_vague = decide_preflight("buat aplikasi", sig_vague, scope_vague, [])
        self.assertEqual(res_vague.decision, BrainDecision.ASK_USER_BEFORE_GENERATE)
        self.assertTrue(res_vague.planning_required)
        self.assertGreater(len(res_vague.scope_analysis.missing_decisions), 0)


if __name__ == "__main__":
    unittest.main()
