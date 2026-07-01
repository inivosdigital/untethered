#!/usr/bin/env python3
"""Cross-language scoring PARITY (Python side).

The Python engine must reproduce the golden verdicts in scoring/parity_fixtures.json —
the SAME golden the extension's parity test asserts. If the Python classifiers ever drift
from the canonical scoring/rules.json (or the rules change without regenerating the
golden), this fails. Together with the JS parity test, this makes it impossible for a
page verdict and a feed verdict to silently disagree on the same posting.

Run:  python3 -m unittest test_scoring_parity
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "scoring", "parity_fixtures.json")


class ScoringParityTests(unittest.TestCase):
    def test_python_engine_matches_golden(self):
        data = json.load(open(FIX))
        self.assertGreaterEqual(len(data["postings"]), 10)
        for post in data["postings"]:
            p = {"title": post["title"], "description": post["description"],
                 "workplace": post["workplace"], "location": post["location"],
                 "pay_hourly": post["payHourly"]}
            harvest.classify(p, harvest.DEFAULT_TITLE_KEYWORDS)
            got = {"rcm": p["_rcm"], "roleArchetype": p["_role_archetype"],
                   "remote": p["_remote"], "pay": p["_pay"],
                   "offshoreResistant": p["_offshore_resistant"],
                   "credential": p["_credential"], "qualifies": p["_qualifies_strict"]}
            self.assertEqual(got, post["expect"],
                             f"Python verdict drift on: {post['title']!r}")


if __name__ == "__main__":
    unittest.main()
