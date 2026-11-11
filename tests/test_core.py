import unittest
import pandas as pd
from dataproof.core import AnalysisError, Config, execute_plan, run, validate_plan, verify


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({"region": ["A", "B", "A"], "sales": [10, 20, 30]})

    def test_filter_and_sum(self):
        plan = {"operation": "sum", "column": "sales", "filters": [{"column": "region", "op": "eq", "value": "A"}], "group_by": []}
        out = execute_plan(plan, self.frame)
        self.assertEqual(out["value"], 40)
        self.assertEqual(out["rows_used"], 2)
        self.assertTrue(verify(plan, self.frame, out)["passed"])

    def test_reject_unknown_column(self):
        with self.assertRaises(AnalysisError):
            validate_plan({"operation": "sum", "column": "profit"}, self.frame)

    def test_detect_corrupt_output(self):
        plan = {"operation": "sum", "column": "sales"}
        self.assertFalse(verify(plan, self.frame, {"value": 999, "rows_used": 3})["passed"])

    def test_offline_pipeline_and_clarification(self):
        answer = run("What is the average sales?", self.frame, Config(provider="heuristic"))
        self.assertEqual(answer["answer"], 20)
        self.assertEqual(answer["status"], "answered")
        self.assertEqual(run("What changed?", self.frame, Config(provider="heuristic"))["status"], "clarify")

    def test_row_count_includes_missing_values(self):
        frame = pd.DataFrame({"a": [1, None, 3], "b": [None, 2, 3]})
        out = execute_plan({"operation": "count", "column": None}, frame)
        self.assertEqual(out["value"], 3)

    def test_nullable_model_list_fields_are_normalized(self):
        plan = {"operation": "sum", "column": "sales", "filters": None, "group_by": None,
                "assumptions": "missing values are ignored"}
        validate_plan(plan, self.frame)
        self.assertEqual(plan["filters"], [])
        self.assertEqual(plan["group_by"], [])
        self.assertEqual(plan["assumptions"], ["missing values are ignored"])


if __name__ == "__main__":
    unittest.main()
