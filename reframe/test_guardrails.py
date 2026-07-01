#!/usr/bin/env python3
"""Unit tests for the deterministic grounding guard - the trust core."""
import unittest

from reframe.guardrails import check_edit
from reframe.schema import Edit

RESUME = (
    "Medical Billing Representative\n"
    "6 years in a hospital business office.\n"
    "Worked accounts receivable follow-up on unpaid hospital claims.\n"
    "Handled denied claims and filed appeals with commercial and Medicare payers.\n"
)


def edit(**kw):
    base = dict(
        field="bullet",
        change_type="reemphasis",
        source_span="",
        before="",
        after="",
        surfaced_keywords=[],
        rationale="",
    )
    base.update(kw)
    return Edit(**base)


class Accepts(unittest.TestCase):
    def test_grounded_relabel(self):
        e = edit(
            field="headline",
            change_type="relabel",
            source_span="Medical Billing Representative",
            before="Medical Billing Representative",
            after="Accounts Receivable / Denials Specialist",
            surfaced_keywords=["accounts receivable", "denials"],
        )
        self.assertEqual(check_edit(e, RESUME), [])

    def test_grounded_reemphasis_keeps_existing_metric(self):
        e = edit(
            source_span="6 years in a hospital business office.",
            before="6 years in a hospital business office.",
            after="6 years of revenue cycle experience in a hospital business office.",
        )
        self.assertEqual(check_edit(e, RESUME), [])

    def test_acronym_grounded_by_expansion(self):
        e = edit(
            source_span="Worked accounts receivable follow-up on unpaid hospital claims.",
            before="Worked accounts receivable follow-up on unpaid hospital claims.",
            after="Owned AR follow-up on unpaid hospital claims.",
        )
        self.assertEqual(check_edit(e, RESUME), [])


class Abstains(unittest.TestCase):
    def test_fabricated_metric(self):
        e = edit(
            source_span="Worked accounts receivable follow-up on unpaid hospital claims.",
            before="Worked accounts receivable follow-up on unpaid hospital claims.",
            after="Reduced accounts receivable aging by 34%.",
        )
        self.assertIn("fabricated_metric:34", check_edit(e, RESUME))

    def test_fabricated_system(self):
        e = edit(
            source_span="Handled denied claims and filed appeals with commercial and Medicare payers.",
            before="Handled denied claims and filed appeals with commercial and Medicare payers.",
            after="Handled denials in Epic and filed appeals with Medicare payers.",
        )
        self.assertIn("fabricated_entity:Epic", check_edit(e, RESUME))

    def test_fabricated_cert(self):
        e = edit(
            source_span="Handled denied claims and filed appeals with commercial and Medicare payers.",
            before="Handled denied claims and filed appeals with commercial and Medicare payers.",
            after="CPC-certified; handled denials and appeals for Medicare payers.",
        )
        self.assertIn("fabricated_entity:CPC", check_edit(e, RESUME))

    def test_ungrounded_span(self):
        e = edit(
            source_span="Managed a team of ten billing specialists.",
            before="Managed a team of ten billing specialists.",
            after="Led accounts receivable for a team of billing specialists.",
        )
        reasons = check_edit(e, RESUME)
        self.assertIn("ungrounded_span", reasons)
        self.assertIn("ungrounded_before", reasons)

    def test_no_op(self):
        e = edit(
            source_span="6 years in a hospital business office.",
            before="6 years in a hospital business office.",
            after="6 years in a hospital business office.",
        )
        self.assertIn("no_op", check_edit(e, RESUME))

    def test_relabel_keyword_not_in_taxonomy(self):
        # keyword is present in `after` but is not an approved search term
        e = edit(
            field="headline",
            change_type="relabel",
            source_span="Medical Billing Representative",
            before="Medical Billing Representative",
            after="Rockstar Billing Ninja",
            surfaced_keywords=["rockstar"],
        )
        self.assertIn("keyword_not_in_taxonomy:rockstar", check_edit(e, RESUME))

    def test_relabel_keyword_absent_from_after(self):
        # an approved keyword is claimed but never actually appears in `after`
        e = edit(
            field="headline",
            change_type="relabel",
            source_span="Medical Billing Representative",
            before="Medical Billing Representative",
            after="Senior Billing Specialist",
            surfaced_keywords=["accounts receivable"],
        )
        self.assertIn("keyword_absent_from_after", check_edit(e, RESUME))

    def test_relabel_requires_keyword(self):
        e = edit(
            field="headline",
            change_type="relabel",
            source_span="Medical Billing Representative",
            before="Medical Billing Representative",
            after="Senior Billing Representative",
            surfaced_keywords=[],
        )
        self.assertIn("relabel_no_keyword", check_edit(e, RESUME))


if __name__ == "__main__":
    unittest.main()
