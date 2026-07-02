#!/usr/bin/env python3
"""Backend proposer proxy for the browser extension.

The extension's side panel must never ship an Anthropic key, so the LLM step is
done here instead: this server holds the ZDR-enabled key (via ANTHROPIC_API_KEY
or an `ant` profile) and exposes one endpoint the panel calls:

    POST /reframe/propose   {resume, mode, target_title?}  ->  {edits: [...]}

The server returns the RAW proposals; the extension's on-device guard validates
every one before anything is shown, so a compromised proxy still cannot make the
panel display a fabricated edit. Run this under the reframe venv (it needs the
anthropic SDK for the default proposer).

Security posture:
  * PII: the resume is never logged, and error responses never echo it - a
    failure returns a generic message, not the request body.
  * CORS: locked to an allowlist (REFRAME_ALLOWED_ORIGINS, comma-separated); an
    unlisted Origin gets no CORS header and the browser blocks the response.
  * This proxy does no auth of its own - put it behind your own gate (Cloudflare
    Access, an API key check, a private network) before exposing it publicly.
  * A request body over MAX_BODY bytes is rejected (413).
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from reframe.engine import MODES

MAX_BODY = 512 * 1024  # 512 KB is far more than any resume; caps abuse


def _default_proposer():
    from reframe.llm import propose  # lazy: needs anthropic + a key at call time

    return propose


def _make_handler(propose_fn, origins):
    class Handler(BaseHTTPRequestHandler):
        server_version = "UntetheredReframeProxy/1"

        def _cors(self):
            origin = self.headers.get("Origin")
            if origin and origin in origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "content-type")

        def _json(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if self.path == "/health":
                return self._json(200, {"status": "ok"})
            if self.path == "/reframe/propose":
                return self._json(405, {"error": "method not allowed"})
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/reframe/propose":
                return self._json(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._json(400, {"error": "invalid length"})
            if n <= 0:
                return self._json(400, {"error": "empty body"})
            if n > MAX_BODY:
                return self._json(413, {"error": "body too large"})
            try:
                data = json.loads(self.rfile.read(n).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._json(400, {"error": "invalid JSON"})

            resume = data.get("resume")
            mode = data.get("mode", "full_reframe")
            target = data.get("target_title")
            if not isinstance(resume, str) or not resume.strip():
                return self._json(400, {"error": "missing resume"})
            if mode not in MODES:
                return self._json(400, {"error": "invalid mode"})
            if mode == "control":
                return self._json(200, {"edits": []})  # baseline - no LLM call

            try:
                proposal = propose_fn(resume, mode, target_title=target)
            except Exception:
                # never surface the resume or an internal trace to the client
                return self._json(502, {"error": "proposer unavailable or declined"})
            return self._json(200, {"edits": [e.model_dump() for e in proposal.edits]})

        def log_message(self, fmt, *args):
            # concise, body-free access log (never the resume)
            import sys
            sys.stderr.write("%s - %s\n" % (self.command, self.path))

    return Handler


def build_server(host="127.0.0.1", port=8781, propose_fn=None, allowed_origins=None):
    """Construct (but do not start) the proxy HTTPServer. ``propose_fn`` is
    injectable for tests; ``allowed_origins`` overrides REFRAME_ALLOWED_ORIGINS."""
    propose_fn = propose_fn or _default_proposer()
    if allowed_origins is None:
        allowed_origins = [
            o.strip() for o in os.environ.get("REFRAME_ALLOWED_ORIGINS", "").split(",") if o.strip()
        ]
    handler = _make_handler(propose_fn, set(allowed_origins))
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Untethered reframe proposer proxy.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8781)
    args = ap.parse_args(argv)

    if not os.environ.get("REFRAME_ALLOWED_ORIGINS"):
        print("WARNING: REFRAME_ALLOWED_ORIGINS is unset - browsers will be CORS-blocked. "
              "Set it to your extension origin, e.g. chrome-extension://<id>.")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("NOTE: no ANTHROPIC_API_KEY/AUTH_TOKEN in env - relying on an `ant` profile if present.")

    server = build_server(args.host, args.port)
    print(f"reframe proposer proxy on http://{args.host}:{args.port}  (POST /reframe/propose)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
