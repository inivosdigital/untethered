#!/usr/bin/env python3
"""Unit tests for the vocabulary + entity-extraction substrate."""
import unittest

from reframe import taxonomy as tx


class NumericTokens(unittest.TestCase):
    def test_extracts_and_normalizes(self):
        self.assertEqual(tx.numeric_tokens("cut A/R by 34% over 6 years"), {"34", "6"})
        self.assertEqual(tx.numeric_tokens("$1,200 and 3.5x"), {"1200", "3.5"})

    def test_empty(self):
        self.assertEqual(tx.numeric_tokens("no digits here"), set())
        self.assertEqual(tx.numeric_tokens(""), set())


class HardEntities(unittest.TestCase):
    def _texts(self, s):
        return {e["text"] for e in tx.hard_entities(s)}

    def test_acronym_extracted_but_generic_allowlisted(self):
        got = tx.hard_entities("CPC coding for a US payer")
        kinds = {(e["text"], e["kind"]) for e in got}
        self.assertIn(("CPC", "acronym"), kinds)
        self.assertNotIn("US", self._texts("CPC coding for a US payer"))

    def test_lexicon_terms(self):
        texts = self._texts("Worked denials in Epic and submitted via Availity")
        self.assertIn("epic", {t.lower() for t in texts})
        self.assertIn("availity", {t.lower() for t in texts})

    def test_named_org_needs_suffix(self):
        # carries an org marker -> extracted
        self.assertIn("Mercy Health System", self._texts("Employed at Mercy Health System"))
        # generic TitleCase role phrase -> NOT extracted (relabel target, not a claim)
        self.assertEqual(self._texts("Accounts Receivable Specialist"), set())


class EntityGrounded(unittest.TestCase):
    def test_acronym_grounded_by_expansion(self):
        ar = {"text": "AR", "kind": "acronym"}
        self.assertTrue(tx.entity_grounded(ar, "handled accounts receivable follow-up"))
        self.assertFalse(tx.entity_grounded(ar, "handled billing follow-up"))

    def test_lexicon_grounded_by_presence(self):
        epic = {"text": "Epic", "kind": "lexicon"}
        self.assertTrue(tx.entity_grounded(epic, "posted in Epic daily"))
        self.assertFalse(tx.entity_grounded(epic, "posted payments daily"))

    def test_target_title_always_grounded(self):
        # a relabel to a taxonomy target is allowed even if not verbatim
        org = {"text": "Accounts Receivable", "kind": "org"}
        self.assertTrue(tx.entity_grounded(org, "resume with no such phrase"))


if __name__ == "__main__":
    unittest.main()
