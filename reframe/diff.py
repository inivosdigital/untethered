#!/usr/bin/env python3
"""Human-readable diff of a reframe result.

Transparency is a feature, not a nicety: the user sees every accepted change,
every keyword it surfaces, AND every edit the guard rejected with the reason. A
reframe the user cannot inspect is a reframe the user cannot trust to send.
"""

_RULE = "-" * 68

_REASON_TEXT = {
    "empty_after": "proposed text was empty",
    "no_op": "did not change anything",
    "ungrounded_span": "anchor span not found verbatim in the resume",
    "ungrounded_before": "original text not found verbatim in the resume",
    "relabel_no_keyword": "relabel surfaced no recruiter keyword",
    "keyword_absent_from_after": "claimed keyword not present in the new text",
}


def _explain(reason):
    if ":" in reason:
        kind, detail = reason.split(":", 1)
        if kind == "fabricated_metric":
            return f"invented metric not in resume: {detail}"
        if kind == "fabricated_entity":
            return f"invented credential/employer not in resume: {detail}"
        if kind == "keyword_not_in_taxonomy":
            return f"keyword outside approved search taxonomy: {detail}"
    return _REASON_TEXT.get(reason, reason)


def render(result):
    """Return a plain-text report of a :class:`reframe.engine.ReframeResult`."""
    lines = [
        _RULE,
        f"RESUME RE-FRAME  |  mode: {result.mode}",
        _RULE,
    ]

    if result.mode == "control":
        lines.append("Control arm: resume left unchanged (A/B baseline).")
        lines.append(_RULE)
        return "\n".join(lines)

    if result.accepted:
        lines.append(f"ACCEPTED CHANGES ({len(result.accepted)}):")
        for i, e in enumerate(result.accepted, 1):
            lines.append("")
            lines.append(f"  {i}. [{e.field} / {e.change_type}]")
            lines.append(f"     - before: {e.before}")
            lines.append(f"     + after:  {e.after}")
            if e.surfaced_keywords:
                lines.append(f"     surfaces: {', '.join(e.surfaced_keywords)}")
            lines.append(f"     why:      {e.rationale}")
    else:
        lines.append("ACCEPTED CHANGES: none survived the grounding guard.")

    hits = result.new_search_hits
    lines.append("")
    lines.append(_RULE)
    if hits:
        lines.append("NEW RECRUITER-SEARCH TERMS NOW PRESENT (were not before):")
        lines.append("  " + ", ".join(hits))
    else:
        lines.append("NEW RECRUITER-SEARCH TERMS: none added.")

    if result.abstained:
        lines.append("")
        lines.append(_RULE)
        lines.append(f"ABSTAINED - DROPPED AS UNGROUNDED ({len(result.abstained)}):")
        for i, (e, reasons) in enumerate(result.abstained, 1):
            lines.append("")
            lines.append(f"  {i}. [{e.field} / {e.change_type}] {e.after}")
            for r in reasons:
                lines.append(f"     x {_explain(r)}")

    if result.mode_filtered:
        lines.append("")
        lines.append(_RULE)
        lines.append(
            f"HELD BACK BY MODE ({len(result.mode_filtered)}) - "
            f"grounded, but out of scope for '{result.mode}'."
        )

    lines.append(_RULE)
    return "\n".join(lines)
