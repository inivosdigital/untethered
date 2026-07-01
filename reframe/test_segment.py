#!/usr/bin/env python3
"""Unit tests for the deterministic segmenter.

Two levels of assertion:
  * the PARTITION CONTRACT (byte-exact, gap-free cover) is checked on every
    fixture - this is the safety bedrock apply relies on;
  * strong field extraction (headline, summary, every bullet) is asserted on the
    heading-tier fixtures. Heuristic/abstain-tier resumes (no headers, two-column)
    are only held to the partition contract, because they degrade to a whole-
    resume fallback by design rather than risk a wrong-narrow assignment.
"""
import json
import os
import unittest

from reframe import segment as seg
from reframe.taxonomy import norm

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "examples", "segment_fixtures.json"), encoding="utf-8") as _f:
    FIXTURES = json.load(_f)


def _assert_partition(tc, doc):
    tc.assertTrue(doc.segments, "must have at least one segment")
    tc.assertEqual(doc.segments[0].char_start, 0)
    tc.assertEqual(doc.segments[-1].char_end, len(doc.source))
    for i in range(1, len(doc.segments)):
        tc.assertEqual(doc.segments[i].char_start, doc.segments[i - 1].char_end)
    recon = "".join(doc.source[s.char_start:s.char_end] for s in doc.segments)
    tc.assertEqual(recon, doc.source)


class PartitionContract(unittest.TestCase):
    def test_every_fixture_is_a_byte_exact_partition(self):
        for f in FIXTURES:
            with self.subTest(f["label"]):
                _assert_partition(self, seg.segment(f["resume_text"]))

    def test_degrades_without_raising(self):
        for junk in ("", "   ", "\n\n\n", "one line no structure at all"):
            with self.subTest(repr(junk)):
                _assert_partition(self, seg.segment(junk))


class HeadingTierExtraction(unittest.TestCase):
    def test_clean_resumes_extract_all_fields(self):
        checked = 0
        for f in FIXTURES:
            doc = seg.segment(f["resume_text"])
            if doc.tier != "heading":
                continue
            checked += 1
            exp = f["expected"]
            with self.subTest(f["label"]):
                self.assertIn(norm(exp["headline"]), norm(doc.field_text("headline")))
                self.assertIn(norm(exp["summary"]), norm(doc.field_text("summary")))
                bullets = norm(doc.field_text("bullet"))
                for b in exp["experience_bullets"]:
                    self.assertIn(norm(b), bullets)
        self.assertGreaterEqual(checked, 4, "expected several heading-tier fixtures")


class SpliceSafety(unittest.TestCase):
    def test_single_column_summary_is_splice_safe(self):
        f = next(x for x in FIXTURES if x["label"] == "colon_suffixed_headers_pipe_skills")
        doc = seg.segment(f["resume_text"])
        summaries = [s for s in doc.segments if s.field == "summary"]
        self.assertTrue(summaries and all(s.splice_safe for s in summaries))

    def test_two_column_interleaved_has_unsafe_segments(self):
        f = next(x for x in FIXTURES if x["label"] == "two_column_flattened_interleaved")
        doc = seg.segment(f["resume_text"])
        # at least one segment must be flagged unsafe so apply falls back safely
        self.assertTrue(any(not s.splice_safe for s in doc.segments))


class Resolve(unittest.TestCase):
    RESUME = (
        "Jane Doe\n"
        "Billing Specialist\n\n"
        "Summary\n"
        "Handled claims for the team every day.\n\n"
        "Experience\n"
        "Acme Health, Billing Specialist (2019-2022)\n"
        "- Handled claims for the team every day.\n"
        "- Posted payments to patient accounts.\n\n"
        "Skills\n"
        "Epic, claim resolution\n"
    )

    def setUp(self):
        self.doc = seg.segment(self.RESUME)

    def test_resolves_unique_phrase_in_its_field(self):
        span = self.doc.resolve("Posted payments to patient accounts.", "bullet")
        self.assertIsNotNone(span)
        self.assertEqual(self.RESUME[span[0]:span[1]], "Posted payments to patient accounts.")

    def test_field_scoping_picks_the_right_duplicate(self):
        # the phrase appears in BOTH summary and a bullet; a bullet-field resolve
        # must land on the bullet, not the earlier summary occurrence.
        span = self.doc.resolve("Handled claims for the team every day.", "bullet")
        self.assertIsNotNone(span)
        # the resolved span must sit after the Experience heading, not in Summary
        exp_at = self.RESUME.index("Experience")
        self.assertGreater(span[0], exp_at)

    def test_absent_field_returns_none(self):
        self.assertIsNone(self.doc.resolve("Handled claims for the team every day.", "skills"))


if __name__ == "__main__":
    unittest.main()
