#!/usr/bin/env python3
"""Tests for the P0-E callback A/B stats + assignment. Stdlib unittest only.

Run:  python3 -m unittest test_p0e -v
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p0e_callback_ab as p0e  # noqa: E402


class Chi2Tests(unittest.TestCase):
    def test_df1_critical_value(self):
        # chi-square df=1 critical value at alpha .05 is 3.8415 -> sf ~= 0.05
        self.assertAlmostEqual(p0e.chi2_sf(3.8415, 1), 0.05, places=3)

    def test_df2_critical_value(self):
        # df=2 critical value at alpha .05 is 5.9915 -> sf ~= 0.05
        self.assertAlmostEqual(p0e.chi2_sf(5.9915, 2), 0.05, places=3)

    def test_df2_closed_form(self):
        # for df=2, sf(x) == exp(-x/2) exactly
        self.assertAlmostEqual(p0e.chi2_sf(2.0, 2), math.exp(-1.0), places=6)

    def test_zero_stat_is_one(self):
        self.assertEqual(p0e.chi2_sf(0.0, 1), 1.0)
        self.assertEqual(p0e.chi2_sf(0.0, 2), 1.0)

    def test_df1_matches_erfc_identity(self):
        # df=1 survival == erfc(sqrt(x/2))
        for x in (0.5, 1.0, 2.7, 6.0):
            self.assertAlmostEqual(p0e.chi2_sf(x, 1), math.erfc(math.sqrt(x / 2)), places=6)


class Chi2TableTests(unittest.TestCase):
    def test_2x2_clear_difference_is_significant(self):
        # control 10/100 vs treat 30/100 -> highly significant
        chi, p = p0e.chi2_2x2_yates(10, 90, 30, 70)
        self.assertIsNotNone(p)
        self.assertLess(p, 0.001)

    def test_2x2_identical_arms_not_significant(self):
        chi, p = p0e.chi2_2x2_yates(10, 90, 10, 90)
        self.assertGreater(p, 0.9)

    def test_2x2_empty_margin_returns_none(self):
        self.assertEqual(p0e.chi2_2x2_yates(0, 0, 5, 5), (None, None))

    def test_omnibus_rxk_df(self):
        chi, df, p = p0e.chi2_rxk([[5, 5, 5], [95, 95, 95]])
        self.assertEqual(df, 2)          # (2-1)*(3-1)
        self.assertAlmostEqual(chi, 0.0, places=6)   # identical columns
        self.assertAlmostEqual(p, 1.0, places=6)


class AssignmentTests(unittest.TestCase):
    def test_within_user_balanced(self):
        import random
        random.seed(1)
        apps = []
        for _ in range(30):
            arm = p0e.assign_arm(apps, "U")
            apps.append({"id": len(apps) + 1, "user": "U", "arm": arm, "callback": None})
        counts = {a: sum(1 for r in apps if r["arm"] == a) for a in p0e.ARMS}
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)  # balanced
        self.assertEqual(sum(counts.values()), 30)

    def test_assignment_is_per_user(self):
        apps = [{"id": i, "user": "A", "arm": "control", "callback": None} for i in range(5)]
        # user B has no history -> should still return a valid arm, not error
        self.assertIn(p0e.assign_arm(apps, "B"), p0e.ARMS)


class ReportTests(unittest.TestCase):
    def test_report_computes_rates_and_status(self):
        apps = []
        # control 4% (2/50), full_reframe 20% (10/50), title_only 10% (5/50)
        def add(arm, n, cb):
            for i in range(n):
                apps.append({"id": len(apps) + 1, "user": "U", "arm": arm,
                             "callback": i < cb})
        add("control", 50, 2)
        add("title_only", 50, 5)
        add("full_reframe", 50, 10)
        rep = p0e.build_report(apps)
        self.assertEqual(rep["per_arm"]["control"]["n"], 50)
        self.assertAlmostEqual(rep["per_arm"]["control"]["rate"], 0.04, places=3)
        self.assertAlmostEqual(rep["per_arm"]["full_reframe"]["rate"], 0.20, places=3)
        self.assertEqual(rep["outcomes_recorded"], 150)
        self.assertIsNotNone(rep["omnibus_p"])
        # a real 4%->20% lift at n=50/arm should read GO (significant + upward)
        self.assertEqual(rep["status"], "go")

    def test_report_empty_is_pending(self):
        rep = p0e.build_report([])
        self.assertEqual(rep["status"], "pending")
        self.assertEqual(rep["outcomes_recorded"], 0)


if __name__ == "__main__":
    unittest.main()
