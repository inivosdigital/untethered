#!/usr/bin/env python3
"""Pay-truth PARITY (Python side) — pay.py must reproduce the golden PayEstimates in
scoring/pay_parity_fixtures.json (the same golden the extension's pay parity test
asserts). Guarantees the trust-critical pay verdict can't diverge between backend and
extension. Run:  python3 -m unittest test_pay_parity"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pay  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "scoring", "pay_parity_fixtures.json")


def run(fx):
    k, inp = fx["kind"], fx["input"]
    if k == "posted-structured":
        return pay.posted_estimate(structured=inp)
    if k == "posted-text":
        return pay.posted_estimate(text=inp)
    if k == "oews":
        return pay.oews_prior(**inp)
    if k == "crowd":
        return pay.crowd_aggregate(inp)
    raise ValueError(k)


class PayParityTests(unittest.TestCase):
    def test_python_pay_engine_matches_golden(self):
        data = json.load(open(FIX))
        self.assertGreaterEqual(len(data["cases"]), 10)
        for c in data["cases"]:
            self.assertEqual(run(c), c["expect"], f"pay verdict drift on {c['id']!r}")


if __name__ == "__main__":
    unittest.main()
