#!/usr/bin/env python3
"""Deterministic guard: validate each LLM-proposed edit against the resume.

This is the load-bearing layer. The LLM is creative and fallible; this layer is
mechanical and testable, and it hard-abstains anything it cannot prove is a
grounded re-label or re-emphasis. It never rewrites text - it only accepts or
rejects, with a reason for every rejection so a human can see what was dropped.

An edit is ACCEPTED only if it passes ALL checks:

  1. structural   - non-empty, actually changes something.
  2. span         - source_span and before are verbatim in the resume.
  3. numeric      - no number in `after` that is absent from the resume
                    (invented metrics are the #1 resume-integrity risk).
  4. entity       - no cert / system / clearinghouse / insurer / code set /
                    named employer in `after` that is absent from the resume
                    (allowing canonical target-title relabels).
  5. relabel      - a relabel must surface at least one approved-taxonomy
                    keyword, and every claimed keyword must be in the taxonomy.

Reasons are stable strings (optionally ``kind:detail``) so tests and the UI can
assert on them.
"""
from reframe import taxonomy
from reframe.taxonomy import norm


def _grounded(span, resume):
    span = (span or "").strip()
    return bool(span) and norm(span) in norm(resume)


def check_edit(edit, resume):
    """Return a de-duplicated list of abstain reasons. Empty list == ACCEPT."""
    reasons = []

    # 1. structural
    if not (edit.after or "").strip():
        reasons.append("empty_after")
    if norm(edit.after) == norm(edit.before):
        reasons.append("no_op")

    # 2. span grounding
    if not _grounded(edit.source_span, resume):
        reasons.append("ungrounded_span")
    if (edit.before or "").strip() and not _grounded(edit.before, resume):
        reasons.append("ungrounded_before")

    # 3. numeric grounding - every number in `after` must exist in the resume
    new_numbers = taxonomy.numeric_tokens(edit.after) - taxonomy.numeric_tokens(resume)
    if new_numbers:
        reasons.append("fabricated_metric:" + ",".join(sorted(new_numbers)))

    # 4. entity grounding - no invented cert / system / insurer / employer
    for ent in taxonomy.hard_entities(edit.after):
        if not taxonomy.entity_grounded(ent, resume):
            reasons.append("fabricated_entity:" + ent["text"])

    # 5. relabel discipline
    if edit.change_type == "relabel":
        if not edit.surfaced_keywords:
            reasons.append("relabel_no_keyword")
        for kw in edit.surfaced_keywords:
            if not taxonomy.taxonomy_phrase(kw):
                reasons.append("keyword_not_in_taxonomy:" + kw)
        present = [kw for kw in edit.surfaced_keywords if norm(kw) in norm(edit.after)]
        if edit.surfaced_keywords and not present:
            reasons.append("keyword_absent_from_after")

    # de-dupe, preserve order
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out
