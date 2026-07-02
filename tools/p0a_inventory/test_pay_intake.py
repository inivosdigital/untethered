#!/usr/bin/env python3
"""Tests for crowdsourced pay-report intake (offline, temp DB)."""
import os
import tempfile
import unittest

import pay_intake
import store


def _rec(**kw):
    base = {"canonicalRole": "denials_appeals", "geo": "US", "remoteMode": "remote",
            "hourly": 38.0, "currency": "USD", "sourceType": "self-reported",
            "contributorId": "c1", "reportedAt": "2026-03-01", "consent": True}
    base.update(kw)
    return base


class Validate(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(pay_intake.validate(_rec()), [])

    def test_missing_required(self):
        r = _rec(); del r["hourly"]
        self.assertTrue(any("hourly" in e for e in pay_intake.validate(r)))

    def test_bad_enums(self):
        self.assertTrue(pay_intake.validate(_rec(remoteMode="anywhere")))
        self.assertTrue(pay_intake.validate(_rec(sourceType="linkedin")))

    def test_hourly_bounds_and_type(self):
        self.assertTrue(pay_intake.validate(_rec(hourly=0.5)))
        self.assertTrue(pay_intake.validate(_rec(hourly=True)))  # bool is not a number here

    def test_consent_type_and_date(self):
        self.assertTrue(pay_intake.validate(_rec(consent="yes")))
        self.assertTrue(pay_intake.validate(_rec(reportedAt="03/01/2026")))

    def test_unknown_field_rejected(self):
        self.assertTrue(any("unknown" in e for e in pay_intake.validate(_rec(salary=100000))))


class Normalize(unittest.TestCase):
    def test_amount_interval_to_hourly(self):
        r = pay_intake.normalize({"amount": 62400, "interval": "year"})
        self.assertAlmostEqual(r["hourly"], 30.0, places=2)
        self.assertNotIn("amount", r)
        self.assertEqual(r["currency"], "USD")


class Submit(unittest.TestCase):
    def setUp(self):
        self.conn = store.connect(os.path.join(tempfile.mkdtemp(), "p.db"))

    def test_valid_is_stored(self):
        self.assertTrue(pay_intake.submit(self.conn, _rec())["ok"])
        self.assertEqual(len(store.pay_reports_for(self.conn, "denials_appeals", "US", "remote")), 1)

    def test_missing_consent_rejected(self):
        res = pay_intake.submit(self.conn, _rec(consent=False))
        self.assertFalse(res["ok"])
        self.assertEqual(len(store.pay_reports_for(self.conn, "denials_appeals", "US", "remote")), 0)

    def test_duplicate_contributor_rejected(self):
        self.assertTrue(pay_intake.submit(self.conn, _rec(contributorId="dup"))["ok"])
        res = pay_intake.submit(self.conn, _rec(contributorId="dup", hourly=40))
        self.assertFalse(res["ok"])
        self.assertTrue(any("duplicate" in e for e in res["errors"]))

    def test_invalid_not_stored(self):
        self.assertFalse(pay_intake.submit(self.conn, _rec(sourceType="bad"))["ok"])


class CellStatus(unittest.TestCase):
    def setUp(self):
        self.conn = store.connect(os.path.join(tempfile.mkdtemp(), "p.db"))

    def _seed_dense(self):
        sources = ["glassdoor", "levels", "paystub", "offer-letter"]
        dates = ["2026-01-15", "2026-02-15", "2026-03-15", "2026-04-15",
                 "2026-05-15", "2026-01-20", "2026-04-20", "2026-05-10"]
        hourly = [34, 36, 38, 40, 35, 37, 39, 41]
        for i in range(8):
            pay_intake.submit(self.conn, _rec(contributorId=f"c{i}", sourceType=sources[i % 4],
                                              reportedAt=dates[i], hourly=hourly[i]))

    def test_abstains_below_gates(self):
        pay_intake.submit(self.conn, _rec())
        rep = pay_intake.cell_status(self.conn, "denials_appeals")
        self.assertFalse(rep["clears_gates"])
        self.assertIsNone(rep["estimate"])
        self.assertTrue(rep["needs"])  # says what is missing

    def test_clears_gates_when_dense(self):
        self._seed_dense()
        rep = pay_intake.cell_status(self.conn, "denials_appeals")
        self.assertTrue(rep["clears_gates"])
        self.assertEqual(rep["contributors"], 8)
        self.assertIsNotNone(rep["estimate"]["floorHourly"])


if __name__ == "__main__":
    unittest.main()
