#!/usr/bin/env python3
"""Vocabulary + entity extraction for the deterministic fabrication guard.

Two data sources, both authoritative and version-controlled:

  * ``scoring/rules.json`` -> ``title_keywords`` is the SAME recruiter-search
    taxonomy the harvester scores against. A reframe may re-label a job to one
    of these target titles (that is the whole point - get found in recruiter
    Boolean search), so a title from this list is NOT treated as a fabricated
    entity even when it is not verbatim in the resume.

  * ``reframe/lexicon.json`` is the RCM claim vocabulary: certs, systems,
    clearinghouses, insurers, code sets, and org-name markers. If reframed text
    names one of these and the resume does not, that is an invented credential.

This module is pure and has no LLM/SDK dependency - it is the substrate the
guardrail layer validates against, and is fully unit-testable on its own.
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_RULES_PATH = os.path.normpath(os.path.join(_HERE, "..", "scoring", "rules.json"))
_LEXICON_PATH = os.path.join(_HERE, "lexicon.json")

with open(_RULES_PATH, encoding="utf-8") as _f:
    _RULES = json.load(_f)
with open(_LEXICON_PATH, encoding="utf-8") as _f:
    LEXICON = json.load(_f)

# The recruiter-search target titles (lowercased phrases).
TARGET_TITLES = [t.lower() for t in _RULES["title_keywords"]]

# Combined claim vocabulary (certs + systems + clearinghouses + insurers + code
# sets), lowercased, longest-first so multi-word phrases match before a token.
# The (-len, alpha) key is DETERMINISTIC so the cross-language guard (the TS port
# in the extension) produces byte-identical fabricated-entity ordering.
_CLAIM_TERMS = sorted(
    {
        t.lower()
        for key in ("certs", "systems", "clearinghouses", "insurers", "codesets")
        for t in LEXICON.get(key, [])
    },
    key=lambda t: (-len(t), t),
)
_GENERIC_ACRONYMS = {a.upper() for a in LEXICON.get("generic_acronyms", [])}
_ORG_SUFFIXES = {s.lower() for s in LEXICON.get("org_suffixes", [])}
_ACRONYM_MAP = {k.upper(): v.lower() for k, v in LEXICON.get("acronym_map", {}).items()}

_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,5}\b")
# 2+ TitleCase tokens in a row - a candidate named organization / product.
_TITLECASE_SEQ_RE = re.compile(r"\b[A-Z][A-Za-z&.'-]+(?:\s+[A-Z][A-Za-z&.'-]+)+\b")
# Numeric claim: a digit run (with optional decimals / thousands separators).
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def norm(text):
    """Lowercase and collapse whitespace - the canonical form for grounding."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def numeric_tokens(text):
    """Set of numeric claims in ``text`` (thousands separators stripped).

    ``$30/hr``, ``30%``, ``3x``, ``5 years`` all reduce to their digit core, so
    a metric can be compared against the resume regardless of surrounding units.
    """
    return {m.group(0).replace(",", "") for m in _NUMBER_RE.finditer(text or "")}


def taxonomy_covered(phrase):
    """True if a target-title phrase is contained in ``phrase`` (e.g. the relabel
    'Accounts Receivable Specialist' is covered by the title 'accounts receivable')."""
    n = norm(phrase)
    return any(t in n for t in TARGET_TITLES)


def taxonomy_phrase(phrase):
    """True if ``phrase`` itself resolves to a target-title term - used to validate
    that a claimed recruiter keyword is really in the approved search vocabulary."""
    n = norm(phrase)
    return any(t in n or n in t for t in TARGET_TITLES)


def _looks_like_org(seq):
    return any(tok.strip(".,").lower() in _ORG_SUFFIXES for tok in seq.split())


def hard_entities(text):
    """Extract 'hard' claims a reframe must not invent, each as {text, kind}.

    kinds:
      * ``acronym``  - all-caps 2-6 char token (cert / code set / system), minus
                       an allowlist of ubiquitous non-claim acronyms.
      * ``lexicon``  - a curated RCM cert/system/clearinghouse/insurer/code set.
      * ``org``      - a multi-word TitleCase sequence carrying an org marker
                       (Health, Systems, Cross, Inc, ...): a candidate employer.

    Generic capitalized role phrases ('Accounts Receivable Specialist') carry no
    org marker and are deliberately NOT extracted - re-labeling to a role is the
    product, so only genuinely claimable named entities are policed here.
    """
    out = []
    seen = set()

    def add(t, kind):
        key = (kind, norm(t) if kind != "acronym" else t.upper())
        if key not in seen:
            seen.add(key)
            out.append({"text": t, "kind": kind})

    for m in _ACRONYM_RE.finditer(text or ""):
        tok = m.group(0)
        if tok.upper() not in _GENERIC_ACRONYMS:
            add(tok, "acronym")

    for term in _CLAIM_TERMS:
        m = re.search(r"\b" + re.escape(term) + r"\b", text or "", re.IGNORECASE)
        if m:
            add(m.group(0), "lexicon")  # keep the resume's surface form (e.g. 'Epic')

    for m in _TITLECASE_SEQ_RE.finditer(text or ""):
        seq = m.group(0)
        if _looks_like_org(seq):
            add(seq, "org")

    return out


def entity_grounded(entity, resume):
    """True if ``entity`` (from :func:`hard_entities`) is supported by the resume.

    An acronym is grounded by the acronym itself OR its mapped expansion (so 'AR'
    is grounded by 'accounts receivable'); everything else by normalized presence.
    A target-title term is always considered grounded (an allowed relabel).
    """
    text, kind = entity["text"], entity["kind"]
    if taxonomy_covered(text):
        return True
    if kind == "acronym":
        if re.search(r"\b" + re.escape(text) + r"\b", resume):
            return True
        expansion = _ACRONYM_MAP.get(text.upper())
        return bool(expansion and expansion in norm(resume))
    return norm(text) in norm(resume)
