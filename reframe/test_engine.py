#!/usr/bin/env python3
"""End-to-end tests: proposer -> guard -> mode-gate -> diff, offline."""
import json
import os
import unittest

from reframe import diff
from reframe.engine import reframe
from reframe.schema import ReframeProposal

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_example():
    with open(os.path.join(_HERE, "examples", "laritza_resume.txt"), encoding="utf-8") as f:
        resume = f.read()
    with open(os.path.join(_HERE, "examples", "laritza_edits.json"), encoding="utf-8") as f:
        proposal = ReframeProposal.model_validate(json.load(f))
    return resume, (lambda r, m, **_: proposal)


class FullReframe(unittest.TestCase):
    def setUp(self):
        self.resume, self.proposer = _load_example()
        self.res = reframe(self.resume, mode="full_reframe", proposer=self.proposer)

    def test_three_grounded_edits_accepted(self):
        self.assertEqual(len(self.res.accepted), 3)
        fields = sorted(e.field for e in self.res.accepted)
        self.assertEqual(fields, ["bullet", "headline", "summary"])

    def test_three_ungrounded_edits_abstained(self):
        self.assertEqual(len(self.res.abstained), 3)
        reason_kinds = {r.split(":", 1)[0] for _, rs in self.res.abstained for r in rs}
        self.assertIn("fabricated_metric", reason_kinds)
        self.assertIn("fabricated_entity", reason_kinds)
        self.assertIn("ungrounded_span", reason_kinds)

    def test_new_search_hits(self):
        # newly-present taxonomy terms only; 'accounts receivable' and 'appeals'
        # were already in the resume body, so they are (correctly) not "new".
        hits = set(self.res.new_search_hits)
        for term in ("denials", "revenue cycle"):
            self.assertIn(term, hits)
        self.assertNotIn("accounts receivable", hits)

    def test_applied_resume_relabels_headline(self):
        self.assertIn("Accounts Receivable / Denials & Appeals Specialist", self.res.applied_resume)
        self.assertNotIn("Medical Billing Representative", self.res.applied_resume)

    def test_original_resume_untouched(self):
        self.assertIn("Medical Billing Representative", self.res.resume)


class TitleOnly(unittest.TestCase):
    def setUp(self):
        self.resume, self.proposer = _load_example()
        self.res = reframe(self.resume, mode="title_only", proposer=self.proposer)

    def test_only_headline_kept(self):
        self.assertEqual(len(self.res.accepted), 1)
        self.assertEqual(self.res.accepted[0].field, "headline")

    def test_grounded_non_headline_held_by_mode(self):
        # summary + bullet were grounded but out of scope for title_only
        self.assertEqual(len(self.res.mode_filtered), 2)

    def test_ungrounded_still_abstained(self):
        self.assertEqual(len(self.res.abstained), 3)


class Control(unittest.TestCase):
    def test_control_never_calls_proposer_and_is_a_no_op(self):
        resume, _ = _load_example()

        def boom(*a, **k):
            raise AssertionError("control must not call the proposer")

        res = reframe(resume, mode="control", proposer=boom)
        self.assertEqual(res.accepted, [])
        self.assertEqual(res.applied_resume, resume)
        self.assertEqual(res.new_search_hits, [])


class Misc(unittest.TestCase):
    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            reframe("x", mode="nope")

    def test_to_dict_roundtrips(self):
        resume, proposer = _load_example()
        d = reframe(resume, mode="full_reframe", proposer=proposer).to_dict()
        self.assertEqual(len(d["accepted"]), 3)
        self.assertEqual(len(d["abstained"]), 3)
        self.assertIn("new_search_hits", d)

    def test_diff_renders_without_em_dash(self):
        resume, proposer = _load_example()
        text = diff.render(reframe(resume, mode="full_reframe", proposer=proposer))
        self.assertIn("ACCEPTED CHANGES", text)
        self.assertIn("ABSTAINED", text)
        self.assertNotIn("—", text)  # no em dash, per house style


if __name__ == "__main__":
    unittest.main()
