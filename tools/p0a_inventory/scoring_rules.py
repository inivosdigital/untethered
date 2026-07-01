#!/usr/bin/env python3
"""Canonical scoring rules, loaded from scoring/rules.json — the SINGLE source of truth
shared with the browser extension (extension/src/scoring/rules.json holds the same
content). harvest.py and any Python scorer import these names so the keyword lists,
signal lists, regexes, and thresholds can never drift from the extension.

Regexes compile case-insensitively and use only the Python/JS-common subset (no
lookbehind). Parity between the two runtimes is enforced by scoring/parity_fixtures.json
plus the parity tests (test_scoring_parity.py here, and the extension's parity test).
"""
import json
import os
import re

RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "scoring", "rules.json")
with open(RULES_PATH) as _f:
    RULES = json.load(_f)

FLOOR_HOURLY = RULES["floor_hourly"]
HOURS_PER_YEAR = RULES["hours_per_year"]
HOURS_PER_DAY = RULES["hours_per_day"]
TITLE_KEYWORDS = [k.lower() for k in RULES["title_keywords"]]
ONSHORE_SIGNALS = RULES["onshore_signals"]
OFFSHORE_SIGNALS = RULES["offshore_signals"]
PAY_DISQUALIFIERS = tuple(RULES["pay_disqualifiers"])
INTERVAL_CODES = RULES["interval_codes"]


def _rx(name):
    return re.compile(RULES["regex"][name], re.I)


RN_GATE = _rx("rn_gate")
DEGREE_GATE = _rx("degree_gate")
HYBRID_FLAGS = _rx("hybrid_flags")
REMOTE_FLAGS = _rx("remote_flags")
NEG_REMOTE_FLAGS = _rx("neg_remote_flags")
REMOTE_ANYWHERE_FLAGS = _rx("remote_anywhere_flags")
SENIORITY_EXCLUDE = _rx("seniority_exclude")
FUNCTION_EXCLUDE = _rx("function_exclude")
LEADER_EXCLUDE = _rx("leader_exclude")
LEADER_KEEP = _rx("leader_keep")
MONEY = _rx("money")
PAY_HOURLY = _rx("pay_hourly")
PAY_RANGE = _rx("pay_range")


def to_hourly(amount, interval_hint=""):
    """Normalize an amount + interval hint to $/hr (shared by the harvester AND the pay
    engine; mirrors extension/src/normalizer.js toHourly). Recognizes English words and
    bare USAJOBS codes; falls back to a magnitude guess for genuinely unknown hints."""
    if amount is None:
        return None
    hint = (interval_hint or "").lower().strip()
    hint = INTERVAL_CODES.get(hint, hint)
    if any(k in hint for k in ("hour", "hr", "/h")):
        return amount
    if any(k in hint for k in ("year", "annual", "annum", "yr", "/y")):
        return amount / HOURS_PER_YEAR
    if "biweek" in hint or "bi-week" in hint or "bi week" in hint:
        return amount * 26 / HOURS_PER_YEAR
    if "month" in hint or "/mo" in hint or "mth" in hint:
        return amount * 12 / HOURS_PER_YEAR
    if "week" in hint or "wk" in hint:
        return amount * 52 / HOURS_PER_YEAR
    if "day" in hint or "daily" in hint or "diem" in hint:
        return amount / HOURS_PER_DAY
    return amount if amount < 1000 else amount / HOURS_PER_YEAR
