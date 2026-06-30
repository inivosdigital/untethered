#!/usr/bin/env python3
"""Tests for the P0-A harvester. Stdlib unittest only — no third-party deps.

Run:  python3 -m unittest -v        (from this directory)
      python3 test_harvest.py
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest  # noqa: E402

HPY = harvest.HOURS_PER_YEAR  # 2080


# ---------------------------------------------------------------------------
# HIGH #1 — to_hourly() must normalize month/week/day/biweekly interval codes
# (Lever sends 'per-month-salary' etc.; USAJOBS sends 'PA'/'PH'/'PD'/'BW').
# ---------------------------------------------------------------------------
class ToHourlyIntervalTests(unittest.TestCase):
    def test_monthly_salary_lever_interval(self):
        # $5000/month -> 5000*12/2080 ~= $28.85/hr, NOT $2.40 (magnitude/2080)
        self.assertAlmostEqual(harvest.to_hourly(5000, "per-month-salary"),
                               5000 * 12 / HPY, places=2)

    def test_weekly_wage_lever_interval(self):
        # $1200/week -> 1200*52/2080 = $30.00/hr, NOT $0.58
        self.assertAlmostEqual(harvest.to_hourly(1200, "per-week-wage"),
                               1200 * 52 / HPY, places=2)

    def test_daily_wage_lever_interval(self):
        # $400/day -> $50/hr (8h day), NOT $400/hr
        self.assertAlmostEqual(harvest.to_hourly(400, "per-day-wage"), 50.0, places=2)

    def test_usajobs_per_day_code(self):
        # 'PD' $300/day -> $37.50/hr, NOT $300/hr
        self.assertAlmostEqual(harvest.to_hourly(300, "PD"), 300 / 8, places=2)

    def test_usajobs_biweekly_code(self):
        # 'BW' $2400 biweekly -> 2400*26/2080 = $30.00/hr
        self.assertAlmostEqual(harvest.to_hourly(2400, "BW"), 2400 * 26 / HPY, places=2)

    # these already pass via the magnitude fallback; keep as regression guards
    def test_usajobs_per_annum_code(self):
        self.assertAlmostEqual(harvest.to_hourly(95000, "PA"), 95000 / HPY, places=2)

    def test_usajobs_per_hour_code(self):
        self.assertEqual(harvest.to_hourly(35, "PH"), 35)

    def test_plain_hour_and_year_words_unchanged(self):
        self.assertEqual(harvest.to_hourly(34, "hour"), 34)
        self.assertAlmostEqual(harvest.to_hourly(70000, "year"), 70000 / HPY, places=2)


# ---------------------------------------------------------------------------
# HIGH #2 — free-text pay extraction must not read bonuses/savings as salary.
# ---------------------------------------------------------------------------
class ParsePayFromTextTests(unittest.TestCase):
    def test_signing_bonus_not_treated_as_pay(self):
        hourly, _ = harvest.parse_pay_from_text("Up to $10,000 signing bonus for new hires")
        self.assertIsNone(hourly)

    def test_savings_claim_not_treated_as_pay(self):
        hourly, _ = harvest.parse_pay_from_text("We saved clients $500,000 last year")
        self.assertIsNone(hourly)

    def test_tuition_reimbursement_not_treated_as_pay(self):
        hourly, _ = harvest.parse_pay_from_text("Generous $5,250 tuition reimbursement")
        self.assertIsNone(hourly)

    def test_explicit_hourly_range_kept(self):
        hourly, _ = harvest.parse_pay_from_text("Pay range $32 - $40 per hour")
        self.assertAlmostEqual(hourly, 40.0, places=2)

    def test_annual_salary_kept(self):
        hourly, _ = harvest.parse_pay_from_text("Salary: $95,000 annually")
        self.assertAlmostEqual(hourly, 95000 / HPY, places=2)


# ---------------------------------------------------------------------------
# HIGH #3 — fetchers must NEVER raise (contract in docstring); a single bad
# record or an unexpected payload shape must be skipped, not crash the run.
# ---------------------------------------------------------------------------
class FetcherRobustnessTests(unittest.TestCase):
    def _patch_http(self, payload):
        return mock.patch.object(harvest, "http_get", return_value=payload)

    def test_lever_non_numeric_salary_does_not_crash(self):
        payload = json.dumps([{
            "id": "1", "text": "Denials Analyst",
            "categories": {"location": "Remote"},
            "salaryRange": {"min": "competitive", "max": "DOE", "interval": "per-year-salary"},
            "descriptionPlain": "Handle complex denials and appeals.",
            "hostedUrl": "https://jobs.lever.co/acme/1",
        }])
        with self._patch_http(payload):
            result = harvest.fetch_lever("acme")  # must not raise
        self.assertEqual(len(result), 1)            # record kept, pay just unknown
        self.assertIsNone(result[0]["pay_hourly"])

    def test_lever_dict_error_body_does_not_crash(self):
        with self._patch_http(json.dumps({"error": "not found"})):
            self.assertEqual(harvest.fetch_lever("acme"), [])

    def test_greenhouse_list_body_does_not_crash(self):
        with self._patch_http(json.dumps(["unexpected"])):
            self.assertEqual(harvest.fetch_greenhouse("tok"), [])

    def test_ashby_dict_without_jobs_does_not_crash(self):
        with self._patch_http(json.dumps({"unexpected": True})):
            self.assertEqual(harvest.fetch_ashby("board"), [])

    def test_usajobs_malformed_remuneration_does_not_crash(self):
        payload = json.dumps({"SearchResult": {"SearchResultItems": [
            {"MatchedObjectDescriptor": {
                "PositionID": "1", "PositionTitle": "AR Analyst",
                "PositionRemuneration": "oops-not-a-list",
            }}]}})
        with self._patch_http(payload):
            result = harvest.fetch_usajobs(["ar"], "key", "e@x.com")  # must not raise
        # the job is kept (pay just unknown), not dropped over a bad pay field
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["pay_hourly"])

    # happy paths still work
    def test_greenhouse_happy_path(self):
        payload = json.dumps({"jobs": [{
            "id": 7, "title": "Revenue Cycle Analyst",
            "location": {"name": "Remote - US"}, "content": "<p>Denials &amp; appeals</p>",
            "absolute_url": "https://boards.greenhouse.io/x/jobs/7", "updated_at": "2026-06-01",
        }]})
        with self._patch_http(payload):
            result = harvest.fetch_greenhouse("x")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Revenue Cycle Analyst")

    def test_lever_happy_path_hourly_salary(self):
        payload = json.dumps([{
            "id": "2", "text": "Patient Access Specialist",
            "categories": {"location": "Remote"}, "workplaceType": "remote",
            "salaryRange": {"min": 31, "max": 36, "interval": "per-hour-wage"},
            "descriptionPlain": "Patient financial counseling.",
            "hostedUrl": "https://jobs.lever.co/acme/2", "createdAt": 1700000000000,
        }])
        with self._patch_http(payload):
            result = harvest.fetch_lever("acme")
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["pay_hourly"], 36.0, places=2)


# ---------------------------------------------------------------------------
# MED #4 — Greenhouse content is HTML-ENTITY-encoded; tags must still strip.
# ---------------------------------------------------------------------------
class StripHtmlTests(unittest.TestCase):
    def test_entity_encoded_html_tags_are_stripped(self):
        out = harvest.strip_html("&lt;div&gt;&lt;p&gt;Denials &amp; appeals&lt;/p&gt;&lt;/div&gt;")
        self.assertEqual(out, "Denials & appeals")

    def test_plain_html_still_stripped(self):
        self.assertEqual(harvest.strip_html("<div><p>Patient access</p></div>"), "Patient access")

    def test_rcm_keyword_matches_through_entity_encoded_inline_tag(self):
        # 'patient access' split by an entity-encoded <strong> tag must still match
        p = harvest.posting(
            "greenhouse", "1", "x", "Specialist", "Remote", "",
            "&lt;p&gt;Handles &lt;strong&gt;patient&lt;/strong&gt; access tasks&lt;/p&gt;")
        self.assertTrue(harvest.f_rcm(p, ["patient access"]))


# ---------------------------------------------------------------------------
# MED #5 — f_remote must handle negation and not over-trigger on geo wording.
# ---------------------------------------------------------------------------
class RemoteClassifierTests(unittest.TestCase):
    def test_negated_remote_not_classified_remote(self):
        p = harvest.posting("x", "1", "e", "CSR", "United States", "",
                            "Remote work is not available for this position.")
        self.assertEqual(harvest.f_remote(p), "hybrid_or_onsite")

    def test_nationwide_located_in_any_state_is_remote(self):
        p = harvest.posting("x", "2", "e", "AR Analyst", "United States", "",
                            "Remote position. Open to candidates located in any US state.")
        self.assertEqual(harvest.f_remote(p), "remote")

    def test_genuine_hybrid_still_flagged(self):
        p = harvest.posting("x", "3", "e", "Biller", "Dallas", "hybrid",
                            "Hybrid role, 3 days per week in office.")
        self.assertEqual(harvest.f_remote(p), "hybrid_or_onsite")


# ---------------------------------------------------------------------------
# MED #6 — offshore-resistance signals must not fire on generic/substring noise.
# ---------------------------------------------------------------------------
class OffshoreResistantTests(unittest.TestCase):
    def test_generic_software_text_not_onshore(self):
        p = harvest.posting("x", "1", "e", "Software Engineer", "Remote", "",
                            "Build complex distributed systems with audit logging and encoding.")
        resistant, on, off = harvest.f_offshore_resistant(p)
        self.assertEqual(on, 0)
        self.assertFalse(resistant)

    def test_real_denials_appeals_still_resistant(self):
        p = harvest.posting("x", "2", "e", "Denials & Appeals Analyst", "Remote", "",
                            "Manage payer denials and file appeals; payer policy disputes.")
        resistant, on, off = harvest.f_offshore_resistant(p)
        self.assertTrue(resistant)
        self.assertGreaterEqual(on, 1)


# ---------------------------------------------------------------------------
# MED #7 — net-new flow must count a posting the run it FIRST qualifies, even
# if it was seen earlier while non-qualifying (e.g. pay was unpublished then).
# ---------------------------------------------------------------------------
class FlowStateTests(unittest.TestCase):
    def _p(self, sid):
        return harvest.posting("greenhouse", sid, "e", "Revenue Cycle Analyst",
                               "Remote", "remote", "Denials and appeals.")

    def test_seen_nonqualifying_then_qualifying_counts_as_net_new(self):
        state = {}
        p = self._p("1")
        # run 1: seen but NOT qualifying -> not net-new, but recorded
        self.assertEqual(harvest.update_flow_state([p], [], state, "2026-06-01"), [])
        self.assertIn("greenhouse:1", state)
        # run 2: now qualifying -> MUST count as net-new
        self.assertEqual(len(harvest.update_flow_state([p], [p], state, "2026-06-02")), 1)
        # run 3: still qualifying -> NOT net-new again
        self.assertEqual(harvest.update_flow_state([p], [p], state, "2026-06-03"), [])

    def test_legacy_flat_state_value_is_migrated(self):
        state = {"greenhouse:9": "2026-05-01"}  # old {key: date} schema
        p = self._p("9")
        new = harvest.update_flow_state([p], [p], state, "2026-06-02")
        self.assertEqual(len(new), 1)
        self.assertIsInstance(state["greenhouse:9"], dict)


# ---------------------------------------------------------------------------
# MED #8 — state writes must be atomic and loads must tolerate a corrupt file.
# ---------------------------------------------------------------------------
class StatePersistenceTests(unittest.TestCase):
    def test_load_state_tolerates_corrupt_file(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "seen.json")
        with open(path, "w") as f:
            f.write("{ this is : not valid json")
        self.assertEqual(harvest.load_state(path), {})  # must not raise

    def test_save_state_roundtrip_no_temp_left(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "state", "seen.json")
        data = {"greenhouse:1": {"first_seen": "2026-06-01", "first_qualified": None}}
        harvest.save_state(path, data)
        self.assertEqual(harvest.load_state(path), data)
        self.assertFalse(os.path.exists(path + ".tmp"))


# ---------------------------------------------------------------------------
# MED #9 — foreign-currency pay must not be normalized as USD and clear $30.
# ---------------------------------------------------------------------------
class CurrencyTests(unittest.TestCase):
    def _patch_http(self, payload):
        return mock.patch.object(harvest, "http_get", return_value=payload)

    def test_lever_foreign_currency_not_counted_as_usd(self):
        payload = json.dumps([{
            "id": "3", "text": "Billing Specialist",
            "categories": {"location": "Remote - India"},
            "salaryRange": {"min": 600000, "max": 1200000, "currency": "INR",
                            "interval": "per-year-salary"},
            "descriptionPlain": "Charge entry and posting.",
            "hostedUrl": "https://jobs.lever.co/acme/3",
        }])
        with self._patch_http(payload):
            result = harvest.fetch_lever("acme")
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["pay_hourly"])  # INR 1.2M/yr must NOT become ~$577/hr

    def test_lever_usd_currency_counted(self):
        payload = json.dumps([{
            "id": "4", "text": "RC Analyst", "categories": {"location": "Remote"},
            "salaryRange": {"min": 65000, "max": 75000, "currency": "USD",
                            "interval": "per-year-salary"},
            "descriptionPlain": "Denials.", "hostedUrl": "https://jobs.lever.co/acme/4",
        }])
        with self._patch_http(payload):
            result = harvest.fetch_lever("acme")
        self.assertAlmostEqual(result[0]["pay_hourly"], 75000 / HPY, places=2)


if __name__ == "__main__":
    unittest.main()
