#!/usr/bin/env python3
"""Tests for the proposer proxy: real HTTP against an ephemeral-port instance
with a mock proposer (no network, no key)."""
import json
import threading
import unittest
import urllib.error
import urllib.request

from reframe import server
from reframe.schema import Edit, ReframeProposal

ALLOWED = "chrome-extension://abcdefg"


def _canned(resume, mode, target_title=None):
    return ReframeProposal(edits=[Edit(
        field="headline", change_type="relabel",
        source_span="Billing Rep", before="Billing Rep",
        after="Accounts Receivable Specialist",
        surfaced_keywords=["accounts receivable"], rationale="x")])


def _boom(resume, mode, target_title=None):
    raise RuntimeError("proposer exploded with the resume in the message: " + resume)


class ProxyBase(unittest.TestCase):
    propose_fn = staticmethod(_canned)
    origins = [ALLOWED]

    def setUp(self):
        self.srv = server.build_server("127.0.0.1", 0, propose_fn=self.propose_fn,
                                       allowed_origins=self.origins)
        self.port = self.srv.server_address[1]
        self.t = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.t.join(timeout=2)

    def req(self, method, path, body=None, headers=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(url, data=data, method=method,
                                   headers=headers or ({"Content-Type": "application/json"} if data else {}))
        try:
            resp = urllib.request.urlopen(r, timeout=5)
            return resp.status, resp.headers, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read().decode()


class Routes(ProxyBase):
    def test_health(self):
        code, _, body = self.req("GET", "/health")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["status"], "ok")

    def test_propose_ok(self):
        code, _, body = self.req("POST", "/reframe/propose",
                                 {"resume": "Billing Rep at a hospital", "mode": "full_reframe"})
        self.assertEqual(code, 200)
        edits = json.loads(body)["edits"]
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0]["after"], "Accounts Receivable Specialist")

    def test_control_skips_llm(self):
        code, _, body = self.req("POST", "/reframe/propose",
                                 {"resume": "Billing Rep", "mode": "control"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["edits"], [])

    def test_get_on_propose_is_405(self):
        self.assertEqual(self.req("GET", "/reframe/propose")[0], 405)

    def test_unknown_path_404(self):
        self.assertEqual(self.req("GET", "/nope")[0], 404)


class Validation(ProxyBase):
    def test_bad_json_400(self):
        url = f"http://127.0.0.1:{self.port}/reframe/propose"
        r = urllib.request.Request(url, data=b"{not json", method="POST",
                                   headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(r, timeout=5)
            self.fail("expected 400")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_missing_resume_400(self):
        self.assertEqual(self.req("POST", "/reframe/propose", {"mode": "full_reframe"})[0], 400)

    def test_bad_mode_400(self):
        self.assertEqual(self.req("POST", "/reframe/propose",
                                  {"resume": "x", "mode": "nope"})[0], 400)

    def test_body_too_large_413(self):
        big = {"resume": "x" * (server.MAX_BODY + 10), "mode": "full_reframe"}
        self.assertEqual(self.req("POST", "/reframe/propose", big)[0], 413)


class Cors(ProxyBase):
    def test_preflight_allowed_origin(self):
        code, headers, _ = self.req("OPTIONS", "/reframe/propose", headers={"Origin": ALLOWED})
        self.assertEqual(code, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), ALLOWED)

    def test_disallowed_origin_gets_no_cors(self):
        _, headers, _ = self.req("POST", "/reframe/propose",
                                 {"resume": "Billing Rep", "mode": "full_reframe"},
                                 {"Content-Type": "application/json", "Origin": "https://evil.example"})
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))


class ProposerFailure(ProxyBase):
    propose_fn = staticmethod(_boom)

    def test_proposer_exception_is_502_without_pii(self):
        code, _, body = self.req("POST", "/reframe/propose",
                                 {"resume": "SECRET-RESUME-TEXT", "mode": "full_reframe"})
        self.assertEqual(code, 502)
        self.assertNotIn("SECRET-RESUME-TEXT", body)  # no PII leak in the error


if __name__ == "__main__":
    unittest.main()
