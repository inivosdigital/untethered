#!/usr/bin/env python3
"""Tests for the reframe <-> P0-E arm-assignment bridge (offline, temp DB)."""
import json
import os
import tempfile
import unittest

import store
import reframe_pipeline as rp
from p0e_callback_ab import ARMS, build_report

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
with open(os.path.join(_ROOT, "reframe", "examples", "laritza_resume.txt"), encoding="utf-8") as _f:
    RESUME = _f.read()
with open(os.path.join(_ROOT, "reframe", "examples", "laritza_edits.json"), encoding="utf-8") as _f:
    _PROPOSAL_JSON = _f.read()


def _proposer():
    from reframe.schema import ReframeProposal
    proposal = ReframeProposal.model_validate(json.loads(_PROPOSAL_JSON))
    return lambda r, m, **_: proposal


class PipelineBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = store.connect(os.path.join(self.tmp, "t.db"))
        self.prop = _proposer()

    def apply(self, user="u1", **kw):
        return rp.apply_and_record(self.conn, user, kw.get("employer", "Acme"),
                                   kw.get("role", "Denials Analyst"), RESUME,
                                   proposer=self.prop)


class ArmDrivesReframe(PipelineBase):
    def test_result_mode_equals_assigned_arm(self):
        for _ in range(6):
            app_id, arm, result = self.apply()
            self.assertIn(arm, ARMS)
            self.assertEqual(result.mode, arm)
            # the reframe honored the arm's scope
            if arm == "control":
                self.assertEqual(result.accepted, [])
            elif arm == "title_only":
                self.assertTrue(all(e.field == "headline" for e in result.accepted))
                self.assertLessEqual(len(result.accepted), 1)
            else:  # full_reframe
                self.assertEqual(len(result.accepted), 3)

    def test_control_is_a_no_op_reframe(self):
        # pre-seed so the least-used arm for u2 is 'control'
        store.add_application(self.conn, {"user": "u2", "arm": "title_only"})
        store.add_application(self.conn, {"user": "u2", "arm": "full_reframe"})
        _, arm, result = self.apply(user="u2")
        self.assertEqual(arm, "control")
        self.assertEqual(result.applied_resume, RESUME)


class RecordingAndBalance(PipelineBase):
    def test_application_is_recorded_with_the_arm(self):
        app_id, arm, _ = self.apply()
        apps = store.list_applications(self.conn)
        rec = next(a for a in apps if a["id"] == app_id)
        self.assertEqual(rec["arm"], arm)
        self.assertEqual(rec["user"], "u1")
        self.assertIsNone(rec["callback"])

    def test_within_user_assignment_stays_balanced(self):
        for _ in range(6):
            self.apply(user="bal")
        counts = {a: 0 for a in ARMS}
        for r in store.list_applications(self.conn):
            if r["user"] == "bal":
                counts[r["arm"]] += 1
        self.assertEqual(set(counts.values()), {2})  # 6 apps -> 2 per arm


class CallbackLoop(PipelineBase):
    def test_callbacks_flow_into_the_p0e_report(self):
        ids = [self.apply()[0] for _ in range(6)]
        # record 2 callbacks, 2 no-callbacks; leave 2 pending
        store.set_callback(self.conn, ids[0], True, "2026-07-01")
        store.set_callback(self.conn, ids[1], True, "2026-07-01")
        store.set_callback(self.conn, ids[2], False, "2026-07-01")
        store.set_callback(self.conn, ids[3], False, "2026-07-01")
        rep = build_report(store.list_applications(self.conn))
        self.assertEqual(rep["total_applications"], 6)
        self.assertEqual(rep["outcomes_recorded"], 4)
        total_cb = sum(rep["per_arm"][a]["cb"] for a in ARMS)
        self.assertEqual(total_cb, 2)


if __name__ == "__main__":
    unittest.main()
