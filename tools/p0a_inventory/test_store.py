#!/usr/bin/env python3
"""Tests for the SQLite store (F3): schema, migration, flow state, run history, the
flow/cohort/density queries, and the pay-report store feeding pay.crowd_aggregate.
Run:  python3 -m unittest test_store"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402
import pay  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "untethered.db")
        self.conn = store.connect(self.db)

    def test_schema_is_idempotent(self):
        store.connect(self.db)  # re-run schema, must not raise
        tables = {r[0] for r in self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"postings", "runs", "applications", "pay_reports"} <= tables)

    def test_migrate_seen_json_preserves_flow_dates(self):
        seen = {"greenhouse:1": {"first_seen": "2026-06-01", "first_qualified": "2026-06-03"},
                "lever:2": {"first_seen": "2026-06-02", "first_qualified": None},
                "ashby:3": "2026-05-01"}  # legacy flat form
        p = os.path.join(self.dir, "seen.json")
        json.dump(seen, open(p, "w"))
        n = store.migrate_seen_json(self.conn, p)
        self.assertEqual(n, 3)
        state = store.load_flow_state(self.conn)
        self.assertEqual(state["greenhouse:1"]["first_qualified"], "2026-06-03")
        self.assertEqual(state["ashby:3"]["first_seen"], "2026-05-01")   # legacy migrated
        # a second migrate is a no-op (table already populated)
        self.assertEqual(store.migrate_seen_json(self.conn, p), 0)

    def test_flow_state_roundtrip_and_weekly_query(self):
        deduped = [
            {"source": "greenhouse", "source_id": "1", "employer": "Acme", "title": "Denials Analyst",
             "url": "u1", "_qualifies_strict": True, "pay_hourly": 41, "pay_ceiling": 45,
             "pay_clears_floor": "yes"},
            {"source": "lever", "source_id": "2", "employer": "Beta", "title": "Biller",
             "url": "u2", "_qualifies_strict": False, "pay_hourly": 22, "pay_ceiling": None,
             "pay_clears_floor": "no"},
        ]
        state = {"greenhouse:1": {"first_seen": "2026-06-30", "first_qualified": "2026-06-30"},
                 "lever:2": {"first_seen": "2026-06-30", "first_qualified": None}}
        store.save_flow_state(self.conn, deduped, state, "2026-06-30")
        back = store.load_flow_state(self.conn)
        self.assertEqual(back["greenhouse:1"]["first_qualified"], "2026-06-30")
        row = self.conn.execute("SELECT employer, last_pay_ceiling FROM postings WHERE key='greenhouse:1'").fetchone()
        self.assertEqual(row["employer"], "Acme")
        self.assertEqual(row["last_pay_ceiling"], 45)
        flow = store.weekly_flow(self.conn)
        self.assertEqual(sum(w["net_new"] for w in flow), 1)  # one qualified posting

    def test_record_run(self):
        summary = {"date": "2026-07-01", "funnel": {"0_total_fetched": 100, "1_rcm_relevant": 10,
                   "6_qualifying_strict": 3}, "straddles_30_qualifying": 2,
                   "pay_unknown_upper_bound_qualifying": 7, "net_new_qualifying_this_run": 3,
                   "pay_coverage": {"postings_with_posted_pay": 60, "postings_pay_unknown": 40}}
        store.record_run(self.conn, summary)
        r = self.conn.execute("SELECT * FROM runs WHERE date='2026-07-01'").fetchone()
        self.assertEqual(r["fetched"], 100)
        self.assertEqual(r["straddles"], 2)

    def test_applications_lifecycle_and_migration(self):
        apps = [{"id": 1, "ts": "t", "user": "u", "employer": "Acme", "role": "Denials",
                 "arm": "control", "callback": None, "callback_date": None}]
        p = os.path.join(self.dir, "applications.json")
        json.dump(apps, open(p, "w"))
        self.assertEqual(store.migrate_apps_json(self.conn, p), 1)
        nid = store.add_application(self.conn, {"user": "u", "employer": "Beta", "role": "AR",
                                                "arm": "full_reframe", "ts": "t2"})
        self.assertEqual(nid, 2)
        self.assertEqual(store.set_callback(self.conn, 2, True, "2026-07-05"), 1)
        got = store.list_applications(self.conn)
        self.assertEqual(len(got), 2)
        self.assertIs(got[1]["callback"], True)

    def test_pay_reports_feed_crowd_aggregate(self):
        for i, (h, st, d) in enumerate([
                (28, "self", "2026-01-10"), (30, "self", "2026-02-01"), (31, "offer", "2026-03-05"),
                (32, "offer", "2026-04-01"), (33, "h1b", "2026-05-02"), (34, "h1b", "2026-06-01"),
                (35, "levels", "2026-06-10"), (40, "levels", "2026-06-20")]):
            store.add_pay_report(self.conn, {"canonicalRole": "denials analyst", "geo": "US",
                "remoteMode": "remote", "hourly": h, "sourceType": st,
                "contributorId": f"c{i}", "reportedAt": d, "consent": True})
        reports = store.pay_reports_for(self.conn, "denials analyst", "US", "remote")
        self.assertEqual(len(reports), 8)
        est = pay.crowd_aggregate(reports)   # density gates pass
        self.assertIsNotNone(est)
        self.assertEqual(est["source"], "crowdsourced")


if __name__ == "__main__":
    unittest.main()
