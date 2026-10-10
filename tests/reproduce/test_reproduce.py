import importlib.util,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"reproduce"))
from run import verify,retrieval_score,rate,tokens,replace_failures,paired_tokens
class ReproductionContract(unittest.TestCase):
    def test_all_public_records_recompute_original_denominators(self):
        r=verify(ROOT)
        self.assertEqual(r["provider_calls"],0)
        self.assertAlmostEqual(r["retrieval47"]["rrf_rerank"]["recall_at5"],.7773049645390071)
        self.assertEqual(r["original_main"]["C-no-reflect"]["task"]["n"],295)
        self.assertEqual(r["original_main"]["C-no-reflect"]["citations"]["n"],242)
        self.assertEqual(r["boundary_refusal"]["C-no-reflect"]["boundary55_action"]["n"],55)
        self.assertEqual(r["query_rewrite"]["C-no-reflect"]["n"],100)
        self.assertEqual(r["classification"]["C-no-reflect"]["raw_model_labels"]["n"],100)
        self.assertEqual(r["compression"]["C-no-reflect"]["service_recovered120"]["completion"]["n"],120)
    def test_spans_require_complete_unicode_coverage_and_choose_one_gold_alternative(self):
        case={"gold_evidence_groups":[{"units":[{"paragraph_id":"p","spans":[{"start":0,"end":3}]}]},{"units":[{"paragraph_id":"q","spans":[{"start":2,"end":4}]}]}]}
        self.assertEqual(retrieval_score(case,[{"paragraph_id":"p","start":0,"end":2}]),0)
        self.assertEqual(retrieval_score(case,[{"paragraph_id":"p","start":0,"end":2},{"paragraph_id":"p","start":2,"end":3}]),1)
        self.assertEqual(retrieval_score(case,[{"paragraph_id":"q","start":2,"end":4}]),1)
    def test_missing_usage_and_pending_are_unknown_not_zero(self):
        self.assertIsNone(tokens({"requests":[{"usage":None}]}))
        self.assertIsNone(rate([True,None,False])["value"])
        self.assertEqual(rate([True,False])["value"],.5)
    def test_retry_only_replaces_original_failed_positions(self):
        old={"x":{"record":{"status":"completed"}}}
        retry=[{"row":{"original_item_id":"x"},"record":{"status":"completed"}}]
        with self.assertRaises(ValueError):replace_failures(old,retry)
        with self.assertRaises(ValueError):replace_failures({},retry)
if __name__=="__main__":unittest.main()
