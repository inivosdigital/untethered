#!/usr/bin/env python3
"""Tests for the income-staircase recommender (offline, temp DB)."""
import os
import tempfile
import unittest

import staircase
import store


class TitleMapping(unittest.TestCase):
    def test_maps_known_titles(self):
        self.assertEqual(staircase.map_title("Medical Billing Representative")["canonical"], "billing_charge")
        self.assertEqual(staircase.map_title("AR Analyst")["canonical"], "claims_ar")
        self.assertEqual(staircase.map_title("Denials Specialist")["canonical"], "denials_appeals")
        self.assertEqual(staircase.map_title("Credentialing Coordinator")["canonical"], "credentialing_enrollment")

    def test_unknown_and_empty_titles(self):
        self.assertIsNone(staircase.map_title("Software Engineer"))
        self.assertIsNone(staircase.map_title(""))
        self.assertIsNone(staircase.map_title(None))


class NextRungs(unittest.TestCase):
    def test_only_higher_tiers_ordered(self):
        cur = staircase.map_title("Medical Billing Representative")  # tier 1
        nxt = staircase.next_rungs(cur, n=10)
        self.assertTrue(all(r["tier"] > cur["tier"] for r in nxt))
        self.assertEqual([r["tier"] for r in nxt], sorted(r["tier"] for r in nxt))

    def test_top_rung_has_no_next(self):
        cur = staircase.map_title("Revenue Cycle Manager")  # 'revenue cycle' -> tier 4
        self.assertEqual(staircase.next_rungs(cur), [])


class Honesty(unittest.TestCase):
    def test_ladder_is_labeled_a_hypothesis(self):
        self.assertIn("hypothesis", staircase.HYPOTHESIS_NOTE.lower())
        self.assertIn("hypothesis", staircase.build_staircase("AR Analyst")["hypothesis"].lower())

    def test_gap_terms_are_never_fabricated(self):
        for title in ("Patient Access", "Medical Billing", "AR Analyst", "Denials Analyst"):
            res = staircase.build_staircase(title)
            for rung in res["next"]:
                for term in rung["gap_to_close"]:
                    self.assertIn(term.lower(), staircase._VOCAB, f"fabricated gap term {term!r}")

    def test_resistance_is_grounded_in_signals(self):
        rungs = {r["canonical"]: r["resistant"] for r in staircase.RUNGS}
        self.assertTrue(rungs["denials_appeals"])   # onshore signal, judgment work
        self.assertFalse(rungs["coding"])           # 'coding' is an offshore signal


class PayHonesty(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store.connect(os.path.join(self.tmp, "s.db"))

    def _seed_dense(self, canonical):
        # >=5 contributors, >=3 month span, no single source > 25%
        sources = ["glassdoor", "levels", "self", "peer"]
        dates = ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15",
                 "2026-05-15", "2026-01-20", "2026-04-20", "2026-05-10"]
        hourly = [34, 36, 38, 40, 35, 37, 39, 41]
        for i in range(8):
            store.add_pay_report(self.conn, {
                "canonicalRole": canonical, "geo": "US", "remoteMode": "remote",
                "hourly": hourly[i], "sourceType": sources[i % 4],
                "contributorId": f"c{i}", "reportedAt": dates[i]})

    def test_pay_abstains_without_data(self):
        res = staircase.build_staircase("AR Analyst", conn=self.conn)
        for rung in res["next"]:
            self.assertEqual(rung["pay"]["status"], "abstain")

    def test_pay_shows_when_density_gated_data_exists(self):
        self._seed_dense("denials_appeals")
        res = staircase.build_staircase("AR Analyst", conn=self.conn)
        denials = next(r for r in res["next"] if r["canonical"] == "denials_appeals")
        self.assertEqual(denials["pay"]["status"], "data")
        self.assertIsNotNone(denials["pay"]["floorHourly"])
        # a rung with no reports still abstains
        other = next(r for r in res["next"] if r["canonical"] != "denials_appeals")
        self.assertEqual(other["pay"]["status"], "abstain")

    def test_no_conn_abstains(self):
        res = staircase.build_staircase("AR Analyst", conn=None)
        self.assertTrue(all(r["pay"]["status"] == "abstain" for r in res["next"]))


if __name__ == "__main__":
    unittest.main()
