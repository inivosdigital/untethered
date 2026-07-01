#!/usr/bin/env python3
"""Tests for the Workday CXS list harvester (Phase-1.1). Network is mocked; verifies the
list parsing, dedup across search terms, pagination stop, and the never-raise contract.
Run:  python3 -m unittest test_workday"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workday_harvest as wh  # noqa: E402

CXS = {"total": 2, "jobPostings": [
    {"title": "Revenue Cycle Analyst", "locationsText": "Remote USA",
     "externalPath": "/job/Remote-USA/Revenue-Cycle-Analyst_R1", "postedOn": "Posted Today",
     "bulletFields": ["R1"]},
    {"title": "Denials Specialist", "locationsText": "Fully Remote - Ohio",
     "externalPath": "/job/Ohio/Denials-Specialist_R2", "postedOn": "Posted 2 Days Ago",
     "bulletFields": ["R2"]},
]}


class WorkdayHarvestTests(unittest.TestCase):
    def _fake_req(self, op, url, data=None, method=None, extra=None, timeout=30):
        if url.endswith("/approot"):
            return 406, b""                      # bootstrap 406s but sets cookies
        if url.endswith("/jobs"):
            page = json.loads(data)
            if page["offset"] == 0:
                return 200, json.dumps(CXS).encode()
            return 200, json.dumps({"total": 2, "jobPostings": []}).encode()
        return 200, b"{}"

    def test_list_parses_and_dedups_across_terms(self):
        with mock.patch.object(wh, "_req", side_effect=self._fake_req):
            jobs = wh.list_jobs("acme", "wd1", "Acme", ["revenue cycle", "denials"])
        self.assertEqual(len(jobs), 2)           # 2 unique, deduped across both queries
        self.assertEqual(jobs[0]["title"], "Revenue Cycle Analyst")
        self.assertEqual(jobs[0]["location"], "Remote USA")
        self.assertTrue(jobs[0]["url"].endswith("/en-US/Acme/job/Remote-USA/Revenue-Cycle-Analyst_R1"))
        self.assertEqual(jobs[1]["source_id"], "/job/Ohio/Denials-Specialist_R2")

    def test_never_raises_on_network_error(self):
        def boom(*a, **k):
            raise RuntimeError("network down")
        with mock.patch.object(wh, "_req", side_effect=boom):
            self.assertEqual(wh.list_jobs("acme", "wd1", "Acme", ["x"]), [])

    def test_non_200_skips_term(self):
        def http500(op, url, **k):
            return (406, b"") if url.endswith("/approot") else (500, b"")
        with mock.patch.object(wh, "_req", side_effect=http500):
            self.assertEqual(wh.list_jobs("acme", "wd1", "Acme", ["x"]), [])


if __name__ == "__main__":
    unittest.main()
