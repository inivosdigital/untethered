#!/usr/bin/env python3
"""Deterministic resume segmenter: clean text -> a ResumeDoc partition.

A ResumeDoc is a total, ordered, non-overlapping, gap-free partition of
``[0, len(source))`` into typed Segments, each carrying EXACT half-open raw
offsets (``source[s.char_start:s.char_end]`` is that segment's text by
construction). This lets a field-scoped edit be spliced into the right region
by offset instead of a global first-occurrence replace, without weakening the
grounding guard (which still validates every edit against the whole resume).

Robustness is a partition invariant, not a hope: construction hard-asserts the
cover, and any failure raises :class:`SegmentError`, which the caller degrades
to a single whole-doc segment (status quo) rather than ship a corrupt map. The
failure direction is always coarser-but-correct, never wrong-narrow - matching
the guard's own accept-or-abstain discipline.

Tiers: (A) heading-anchored when >= 2 canonical section headers are found;
(B) a light layout heuristic otherwise; (C) one whole-doc 'other' if neither is
confident. A ``splice_safe=False`` segment (e.g. two-column-flattened text whose
field content is not contiguous in the raw string) disables offset splicing for
that field, so application falls back to the whole-resume replace - identical to
today's behavior, never a wrong-region splice.
"""
import re
from dataclasses import dataclass, field as dc_field
from typing import List, Optional, Tuple

from reframe.taxonomy import norm

# Segment fields. headline/summary/skills/bullet map to schema.FieldName; the
# rest are coarser scoping/abstain regions that no Edit.field targets, so they
# act as negative space that keeps a targeted edit from bleeding into them.
_HEADLINE, _SUMMARY, _EXPERIENCE, _BULLET, _SKILLS, _EDUCATION, _OTHER = (
    "headline", "summary", "experience", "bullet", "skills", "education", "other"
)

# Section-header synonyms -> canonical field. The gate is a WHOLE-LINE match
# against THIS dictionary, never the RCM title taxonomy: words like
# 'collections' or 'appeals' appear in bullets, so a contains-matcher would
# spawn phantom sections.
_HEADER_SYNONYMS = {
    "summary": _SUMMARY, "professional summary": _SUMMARY, "profile": _SUMMARY,
    "professional profile": _SUMMARY, "career summary": _SUMMARY,
    "objective": _SUMMARY, "about": _SUMMARY, "about me": _SUMMARY,
    "overview": _SUMMARY, "professional overview": _SUMMARY, "snapshot": _SUMMARY,
    "experience": _EXPERIENCE, "work experience": _EXPERIENCE,
    "professional experience": _EXPERIENCE, "employment": _EXPERIENCE,
    "employment history": _EXPERIENCE, "work history": _EXPERIENCE,
    "career history": _EXPERIENCE, "professional background": _EXPERIENCE,
    "relevant experience": _EXPERIENCE,
    "skills": _SKILLS, "core skills": _SKILLS, "technical skills": _SKILLS,
    "key skills": _SKILLS, "core competencies": _SKILLS, "competencies": _SKILLS,
    "areas of expertise": _SKILLS, "expertise": _SKILLS,
    "proficiencies": _SKILLS, "skills & abilities": _SKILLS,
    "education": _EDUCATION, "education & training": _EDUCATION,
    "academic background": _EDUCATION,
    "certifications": _OTHER, "licenses": _OTHER,
    "certifications & licenses": _OTHER, "licenses & certifications": _OTHER,
    "awards": _OTHER, "affiliations": _OTHER, "references": _OTHER,
    "volunteer": _OTHER, "professional affiliations": _OTHER, "contact": _OTHER,
}

_BULLET_RE = re.compile(r"^\s*([-*•·▪◦‣–—]|\d+[.)])\s+")
_UNDERLINE_RE = re.compile(r"^\s*[-=_]{3,}\s*$")
_COLGAP_RE = re.compile(r"\S {3,}\S")  # a mid-line column gap (>=3 spaces)
_CONTACT_RE = re.compile(
    r"(@|https?://|www\.|linkedin\.com|\b\d{3}[)\-.\s]\s*\d{3}[\-.\s]\d{4}\b)", re.I
)
_YEARISH_RE = re.compile(r"\b(19|20)\d{2}\b|\bpresent\b|\bcurrent\b", re.I)


class SegmentError(Exception):
    """Raised when the partition invariants cannot be satisfied."""


def flex_pattern(text):
    """Compile ``text`` into a whitespace-flexible, word-boundary-anchored regex.

    Tokens are joined by ``\\s+`` (so a phrase wrapped across lines still matches)
    and flanked by ``(?<!\\w)`` / ``(?!\\w)`` (so a match is never part of a longer
    word - ``coding`` will not match inside ``Transcoding``). Returns None for
    empty/whitespace-only input.
    """
    toks = [re.escape(t) for t in (text or "").split()]
    if not toks:
        return None
    return re.compile(r"(?<!\w)" + r"\s+".join(toks) + r"(?!\w)")


@dataclass
class Segment:
    field: str
    char_start: int
    char_end: int
    normalized_text: str
    confidence: str
    splice_safe: bool
    has_heading: bool = False
    parent_idx: Optional[int] = None


@dataclass
class ResumeDoc:
    source: str
    segments: List[Segment]
    tier: str

    def field_windows(self, field):
        return [(s.char_start, s.char_end) for s in self.segments if s.field == field]

    def field_text(self, field):
        return "\n".join(
            s.normalized_text for s in self.segments
            if s.field == field and s.normalized_text
        )

    def resolve(self, before, field, source_span=None):
        """Locate ``before`` inside the raw windows of ``field`` and return its
        exact ``(start, end)`` in ``source``, or None to defer to the caller's
        whole-resume fallback.

        Whitespace-flexible (so a phrase wrapped across lines still matches) and
        word-boundary-anchored (so ``coding`` never matches inside ``Transcoding``
        and splices into the middle of a word). On >1 candidate, ``source_span``
        disambiguates by containment (the candidate must sit inside a source_span
        match); still ambiguous -> None. Only splice_safe segments are eligible,
        so a wrong-region splice on interleaved (two-column) text is impossible.
        """
        if not (before or "").strip():
            return None
        pat = flex_pattern(before)
        if pat is None:
            return None
        cands = []
        for s in self.segments:
            if s.field != field or not s.splice_safe:
                continue
            for m in pat.finditer(self.source, s.char_start, s.char_end):
                cands.append((m.start(), m.end()))
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1 and source_span:
            span_pat = flex_pattern(source_span)
            if span_pat is not None:
                matches = list(span_pat.finditer(self.source))
                narrowed = [
                    c for c in cands
                    if any(m.start() <= c[0] and c[1] <= m.end() for m in matches)
                ]
                if len(narrowed) == 1:
                    return narrowed[0]
        return None


# --------------------------------------------------------------------------- #
# Line indexing
# --------------------------------------------------------------------------- #

@dataclass
class _Line:
    idx: int
    raw: str
    char_start: int
    char_end: int
    text: str = ""          # raw minus trailing newline
    stripped: str = ""
    is_blank: bool = False
    is_bullet: bool = False
    is_underline: bool = False
    is_contact: bool = False


def _index_lines(source):
    lines, off = [], 0
    for i, raw in enumerate(source.splitlines(keepends=True)):
        text = raw.rstrip("\n")
        stripped = text.strip()
        lines.append(_Line(
            idx=i, raw=raw, char_start=off, char_end=off + len(raw),
            text=text, stripped=stripped,
            is_blank=(stripped == ""),
            is_bullet=bool(_BULLET_RE.match(text)),
            is_underline=bool(_UNDERLINE_RE.match(text)),
            is_contact=bool(_CONTACT_RE.search(text)),
        ))
        off += len(raw)
    # exact reconstruction guarantee for the line index itself
    if "".join(l.raw for l in lines) != source:
        raise SegmentError("line index does not reconstruct the source")
    return lines


def _heading_field(line):
    """Canonical field if this line is a section header, else None."""
    if line.is_blank or line.is_bullet:
        return None
    s = line.stripped.rstrip(":").strip()
    if not s or len(s) > 40 or len(s.split()) > 5:
        return None
    if s.lower().endswith("."):
        return None
    return _HEADER_SYNONYMS.get(s.lower())


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #

def _dewrap(lines, lo, hi, strip_bullet=False, skip_heading=False):
    """Join the body lines [lo, hi) into a single normalized string."""
    parts = []
    started = False
    for l in lines[lo:hi]:
        if l.is_blank or l.is_underline:
            continue
        if skip_heading and not started and _heading_field(l) is not None:
            started = True
            continue
        started = True
        t = l.text
        if strip_bullet:
            t = _BULLET_RE.sub("", t, count=1)
        parts.append(t.strip())
    return " ".join(p for p in parts if p)


_TITLE_SPLIT_RE = re.compile(r"\s*[|·•●∙‖—–]\s*|\s{2,}")


def _extract_title(text):
    """Pull the current-title text out of a headline line.

    A pure title line (no contact info) is kept whole, internal separators and
    all ('Certified Coder (CPC) | Risk Adjustment Coder'). A line that also
    carries contact info ('Charge Capture Analyst - email - city', or a
    two-column 'Title      email') yields just its leading non-contact segment.
    """
    text = (text or "").strip()
    if not text:
        return None
    if not _CONTACT_RE.search(text):
        return text if len(text) <= 70 else None
    for part in _TITLE_SPLIT_RE.split(text):
        part = part.strip()
        if part and not _CONTACT_RE.search(part):
            return part if len(part) <= 70 else None
        if part:
            return None  # leading segment is itself contact -> no title here
    return None


def _title_focus(lines, lo, hi):
    """The current-title line in a headline region: the first title found after
    the name line. Falls back to the name line."""
    body = [l for l in lines[lo:hi] if not l.is_blank]
    if not body:
        return ""
    for l in body[1:]:  # skip the name (first non-blank line)
        if l.is_bullet:
            continue
        title = _extract_title(l.text)
        if title:
            return title
    return body[0].stripped


def _has_columns(lines, lo, hi):
    """True if this line range looks like flattened two-column text (several
    lines with a mid-line whitespace gap). Such text is not contiguous in raw,
    so offset splicing must be disabled for it."""
    body = [l for l in lines[lo:hi] if not l.is_blank and not l.is_underline]
    if len(body) < 2:
        return False
    gapped = sum(1 for l in body if _COLGAP_RE.search(l.text))
    return gapped >= 2 and gapped >= 0.4 * len(body)


def _make(field, lines, lo, hi, *, conf, source, normalized=None,
          strip_bullet=False, skip_heading=False, has_heading=False):
    if hi <= lo:
        raise SegmentError(f"empty segment range [{lo}, {hi})")
    start = lines[lo].char_start
    end = lines[hi - 1].char_end
    if normalized is None:
        normalized = _dewrap(lines, lo, hi, strip_bullet, skip_heading)
    # splice-safe only when the field text is contiguous in the raw span AND the
    # region is not two-column-flattened; otherwise apply falls back safely.
    safe = (bool(normalized)
            and norm(normalized) in norm(source[start:end])
            and not _has_columns(lines, lo, hi))
    return Segment(field, start, end, normalized, conf, safe, has_heading)


def _split_experience(lines, lo, hi, source):
    """Tile an experience section into entry ('experience') and 'bullet' segments,
    contiguously, so a bullet edit resolves to one line. Non-boundary lines
    (wrapped continuation, blanks) attach to the current segment."""
    # boundary = a bullet line, or a non-bullet entry-header line (date/company)
    bounds = []
    for i in range(lo, hi):
        l = lines[i]
        if l.is_blank or l.is_underline:
            continue
        if _heading_field(l) is not None and i == lo:
            continue  # the section heading itself
        if l.is_bullet:
            bounds.append((i, _BULLET))
        elif _YEARISH_RE.search(l.text) or ("," in l.stripped and not l.is_contact):
            bounds.append((i, _EXPERIENCE))
    if not bounds:
        return [_make(_EXPERIENCE, lines, lo, hi, conf="medium", source=source,
                      skip_heading=True, has_heading=True)]
    segs, first = [], bounds[0][0]
    # the heading + any preamble up to the first boundary is one experience span
    if first > lo:
        segs.append(_make(_EXPERIENCE, lines, lo, first, conf="medium",
                          source=source, skip_heading=True, has_heading=True))
    for k, (bi, kind) in enumerate(bounds):
        nxt = bounds[k + 1][0] if k + 1 < len(bounds) else hi
        segs.append(_make(kind, lines, bi, nxt, conf="medium", source=source,
                          strip_bullet=(kind == _BULLET)))
    return segs


def _split_preamble(lines, lo, hi, source, has_summary_section):
    """The block before the first heading -> a headline segment, plus a summary
    segment if a heading-less prose paragraph follows the contact/title block and
    no explicit Summary section exists elsewhere.

    Returns [] when the range is empty (the resume leads with a heading, so there
    is no preamble and therefore no headline segment)."""
    if lo >= hi:
        return []
    prose = None
    seen_nonblank = 0
    for i in range(lo, hi):
        l = lines[i]
        if l.is_blank:
            continue
        seen_nonblank += 1
        if seen_nonblank >= 2 and not l.is_contact and not l.is_bullet and (
            len(l.stripped) > 55 or l.stripped.endswith((".", "!"))
        ):
            prose = i
            break
    if has_summary_section or prose is None:
        title = _title_focus(lines, lo, hi)
        return [_make(_HEADLINE, lines, lo, hi, conf="high", source=source,
                      normalized=title)]
    title = _title_focus(lines, lo, prose)
    head = _make(_HEADLINE, lines, lo, prose, conf="high", source=source,
                 normalized=title)
    summ = _make(_SUMMARY, lines, prose, hi, conf="medium", source=source)
    return [head, summ]


# --------------------------------------------------------------------------- #
# Tiers
# --------------------------------------------------------------------------- #

def _tier_a(lines, headings, source):
    """headings: list of (line_idx, canonical_field). Build heading-anchored
    sections: preamble -> headline(+summary), then each heading to the next."""
    segs = []
    first = headings[0][0]
    has_summary = any(f == _SUMMARY for _, f in headings)
    segs.extend(_split_preamble(lines, 0, first, source, has_summary))
    for k, (hi_line, fld) in enumerate(headings):
        end_line = headings[k + 1][0] if k + 1 < len(headings) else len(lines)
        if fld == _EXPERIENCE:
            segs.extend(_split_experience(lines, hi_line, end_line, source))
        else:
            segs.append(_make(fld, lines, hi_line, end_line, conf="high",
                              source=source, skip_heading=True, has_heading=True))
    return segs


def _tier_b(lines, source):
    """No reliable headers: keep the leading block as headline (+ optional prose
    summary) and lump the remainder into one coarse 'other' region. Coarse but
    never wrong-narrow."""
    n = len(lines)
    # end of the headline/contact block: first prose paragraph or first bullet
    body_start = n
    seen = 0
    for i in range(n):
        l = lines[i]
        if l.is_blank:
            continue
        seen += 1
        if seen >= 2 and (l.is_bullet or len(l.stripped) > 55
                          or l.stripped.endswith((".", "!"))):
            body_start = i
            break
    if body_start >= n:
        return [_make(_HEADLINE, lines, 0, n, conf="low", source=source,
                      normalized=_title_focus(lines, 0, n))]
    head = _make(_HEADLINE, lines, 0, body_start, conf="low", source=source,
                 normalized=_title_focus(lines, 0, body_start))
    rest = _make(_OTHER, lines, body_start, n, conf="low", source=source)
    return [head, rest]


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _assemble(segs, source):
    """Sort, close gaps into the preceding segment, and hard-assert the
    partition covers [0, len(source)) byte-exactly."""
    segs = sorted(segs, key=lambda s: s.char_start)
    if not segs:
        raise SegmentError("no segments produced")
    if segs[0].char_start != 0:
        segs[0] = _stretch(segs[0], 0, segs[0].char_end)
    for i in range(1, len(segs)):
        prev, cur = segs[i - 1], segs[i]
        if cur.char_start != prev.char_end:
            # fold any gap (blank lines / rules between sections) into prev
            segs[i - 1] = _stretch(prev, prev.char_start, cur.char_start)
    last = segs[-1]
    if last.char_end != len(source):
        segs[-1] = _stretch(last, last.char_start, len(source))
    # invariants
    if segs[0].char_start != 0 or segs[-1].char_end != len(source):
        raise SegmentError("partition does not cover the source")
    for i in range(1, len(segs)):
        if segs[i].char_start != segs[i - 1].char_end:
            raise SegmentError("partition has a gap or overlap")
    if "".join(source[s.char_start:s.char_end] for s in segs) != source:
        raise SegmentError("partition does not reconstruct the source")
    return segs


def _stretch(seg, start, end):
    return Segment(seg.field, start, end, seg.normalized_text, seg.confidence,
                   seg.splice_safe, seg.has_heading, seg.parent_idx)


def segment(source):
    """Segment a clean resume string into a :class:`ResumeDoc`.

    Never raises: on any internal failure it degrades to a single whole-doc
    'other' segment (status quo), so a caller can always trust the partition.
    """
    if not source:
        return ResumeDoc(source, [Segment(_OTHER, 0, 0, "", "low", False)], "abstain")
    try:
        lines = _index_lines(source)
        headings = [(l.idx, f) for l in lines if (f := _heading_field(l)) is not None]
        canonical = [h for h in headings if h[1] != _OTHER]
        if len(canonical) >= 2:
            segs, tier = _tier_a(lines, headings, source), "heading"
        else:
            segs, tier = _tier_b(lines, source), "heuristic"
        segs = _assemble(segs, source)
        return ResumeDoc(source, segs, tier)
    except (SegmentError, IndexError, ValueError):
        whole = Segment(_OTHER, 0, len(source), norm(source), "low", False)
        return ResumeDoc(source, [whole], "abstain")
