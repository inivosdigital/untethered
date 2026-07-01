#!/usr/bin/env python3
"""Apply-layer tests: field-scoped, offset-safe splicing vs. the fallback.

The headline result: when the same phrase lives in two fields, a field-scoped
edit lands in the RIGHT region, where the old global first-occurrence replace
would have hit the wrong one.
"""
import unittest

from reframe.engine import apply_edits
from reframe.schema import Edit
from reframe.segment import segment

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


def edit(field, before, after, **kw):
    return Edit(field=field, change_type=kw.get("change_type", "reemphasis"),
                source_span=kw.get("source_span", before), before=before, after=after,
                surfaced_keywords=kw.get("surfaced_keywords", []), rationale="")


class WrongRegionFix(unittest.TestCase):
    def setUp(self):
        self.doc = segment(RESUME)

    def test_field_scoped_edit_lands_in_the_bullet_not_the_summary(self):
        e = edit("bullet", "Handled claims for the team every day.",
                 "Resolved denials and appeals daily.")
        out = apply_edits(RESUME, [e], self.doc)
        # the SUMMARY occurrence is untouched...
        self.assertIn("Summary\nHandled claims for the team every day.", out)
        # ...and the BULLET occurrence is the one that changed.
        self.assertIn("- Resolved denials and appeals daily.", out)
        self.assertNotIn("- Handled claims for the team every day.", out)

    def test_doc_mode_differs_from_the_global_fallback_here(self):
        # doc=None hits the FIRST occurrence (summary) - the wrong region.
        e = edit("bullet", "Handled claims for the team every day.",
                 "Resolved denials and appeals daily.")
        doc_out = apply_edits(RESUME, [e], self.doc)
        global_out = apply_edits(RESUME, [e], None)
        self.assertNotEqual(doc_out, global_out)
        self.assertIn("Summary\nResolved denials and appeals daily.", global_out)


class OffsetSafety(unittest.TestCase):
    def setUp(self):
        self.doc = segment(RESUME)

    def test_multiple_edits_all_land(self):
        edits = [
            edit("headline", "Billing Specialist", "Accounts Receivable Specialist",
                 change_type="relabel", surfaced_keywords=["accounts receivable"]),
            edit("bullet", "Posted payments to patient accounts.",
                 "Resolved denials across commercial payers."),
        ]
        out = apply_edits(RESUME, edits, self.doc)
        self.assertIn("Accounts Receivable Specialist", out)
        self.assertIn("Resolved denials across commercial payers.", out)

    def test_unique_phrase_equals_global_replace(self):
        # when `before` is unique, field-scoped and global apply must agree.
        e = edit("skills", "Epic, claim resolution", "Epic, Cerner, claim resolution")
        self.assertEqual(
            apply_edits(RESUME, [e], self.doc),
            apply_edits(RESUME, [e], None),
        )

    def test_field_mismatch_falls_back_not_crashes(self):
        # field='summary' but the text only exists as a bullet -> resolve misses,
        # fallback still applies it (global first occurrence), never raises.
        e = edit("summary", "Posted payments to patient accounts.", "Reconciled daily batches.")
        out = apply_edits(RESUME, [e], self.doc)
        self.assertIn("Reconciled daily batches.", out)


if __name__ == "__main__":
    unittest.main()
