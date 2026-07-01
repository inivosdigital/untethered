#!/usr/bin/env python3
"""SQLite persistence (Foundation F3) — the queryable backbone the flat CSV/JSON files
could not provide. Answers the three metrics the thesis depends on:
  * net-new FLOW over time      (postings.first_qualified)
  * callback A/B cohorts        (applications)
  * crowdsourced-pay density    (pay_reports, per canonical_role x geo x remote_mode)

Stdlib sqlite3 only. DB lives at data/untethered.db (gitignored). Existing seen.json and
p0e/applications.json are migrated once, preserving flow continuity.

Postgres path: the schema is standard except the SQLite-isms noted inline
(AUTOINCREMENT -> SERIAL/IDENTITY; "INSERT OR REPLACE"/"ON CONFLICT ... DO UPDATE" is
already ANSI-ish; strftime week bucketing -> date_trunc). Swap connect() for a psycopg
connection and those three spots and the rest ports unchanged.
"""
import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
  key TEXT PRIMARY KEY,               -- source:source_id
  source TEXT, employer TEXT, title TEXT, url TEXT,
  first_seen TEXT, last_seen TEXT,
  first_qualified TEXT,               -- date first strict-qualified (the FLOW signal)
  last_qualifies INTEGER DEFAULT 0,
  last_pay_hourly REAL, last_pay_ceiling REAL, last_clears_floor TEXT
);
CREATE INDEX IF NOT EXISTS idx_postings_first_qualified ON postings(first_qualified);

CREATE TABLE IF NOT EXISTS runs (
  date TEXT PRIMARY KEY, generated_at TEXT,
  fetched INTEGER, rcm INTEGER, ic_archetype INTEGER, remote INTEGER, pay_ge30 INTEGER,
  offshore_resistant INTEGER, qualifying INTEGER, straddles INTEGER, upper INTEGER,
  net_new INTEGER, pay_with INTEGER, pay_unknown INTEGER
);

CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY,             -- P0-E: caller assigns the id
  ts TEXT, user TEXT, employer TEXT, role TEXT,
  arm TEXT, callback INTEGER, callback_date TEXT
);

CREATE TABLE IF NOT EXISTS pay_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,   -- Postgres: SERIAL/GENERATED
  canonical_role TEXT, geo TEXT, remote_mode TEXT, hourly REAL, currency TEXT,
  source_type TEXT, contributor_id TEXT, reported_at TEXT, consent INTEGER, note TEXT
);
CREATE INDEX IF NOT EXISTS idx_pay_reports_cell ON pay_reports(canonical_role, geo, remote_mode);
"""


def default_db_path():
    """SQLite must live on LOCAL disk — the project's data/ is on a CIFS/SMB mount where
    byte-range locking fails ('database is locked'). Default to a local XDG data dir;
    override with $UNTETHERED_DB. The CSV/summary snapshots still go under --out-dir."""
    env = os.environ.get("UNTETHERED_DB")
    if env:
        return env
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "untethered", "untethered.db")


def connect(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# One-time migrations from the legacy flat files (preserve flow continuity)
# ---------------------------------------------------------------------------
def migrate_seen_json(conn, seen_path):
    if conn.execute("SELECT 1 FROM postings LIMIT 1").fetchone():
        return 0  # already populated
    if not os.path.exists(seen_path):
        return 0
    try:
        with open(seen_path) as f:
            seen = json.load(f)
    except (ValueError, OSError):
        return 0
    rows = []
    for key, rec in seen.items():
        if isinstance(rec, dict):
            fs, fq = rec.get("first_seen"), rec.get("first_qualified")
        else:  # legacy flat {key: date}
            fs, fq = (rec if isinstance(rec, str) else None), None
        rows.append((key, key.split(":", 1)[0], fs, fs, fq))
    conn.executemany(
        "INSERT OR IGNORE INTO postings(key, source, first_seen, last_seen, first_qualified) "
        "VALUES (?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def migrate_apps_json(conn, apps_path):
    if conn.execute("SELECT 1 FROM applications LIMIT 1").fetchone():
        return 0
    if not os.path.exists(apps_path):
        return 0
    try:
        with open(apps_path) as f:
            apps = json.load(f)
    except (ValueError, OSError):
        return 0
    for a in apps:
        conn.execute(
            "INSERT OR IGNORE INTO applications(id, ts, user, employer, role, arm, callback, callback_date) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (a.get("id"), a.get("ts"), a.get("user"), a.get("employer"), a.get("role"),
             a.get("arm"), (None if a.get("callback") is None else int(bool(a["callback"]))),
             a.get("callback_date")))
    conn.commit()
    return len(apps)


# ---------------------------------------------------------------------------
# Flow state (replaces seen.json) — same dict shape update_flow_state expects
# ---------------------------------------------------------------------------
def load_flow_state(conn):
    """{key: {first_seen, first_qualified}} — the shape harvest.update_flow_state mutates."""
    state = {}
    for r in conn.execute("SELECT key, first_seen, first_qualified FROM postings"):
        state[r["key"]] = {"first_seen": r["first_seen"], "first_qualified": r["first_qualified"]}
    return state


def save_flow_state(conn, deduped, state, today):
    """Upsert every posting seen this run with its meta + first_seen/first_qualified."""
    for p in deduped:
        key = f"{p['source']}:{p['source_id']}"
        rec = state.get(key, {})
        conn.execute(
            "INSERT INTO postings(key, source, employer, title, url, first_seen, last_seen, "
            "  first_qualified, last_qualifies, last_pay_hourly, last_pay_ceiling, last_clears_floor) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET employer=excluded.employer, title=excluded.title, "
            "  url=excluded.url, last_seen=excluded.last_seen, first_qualified=excluded.first_qualified, "
            "  last_qualifies=excluded.last_qualifies, last_pay_hourly=excluded.last_pay_hourly, "
            "  last_pay_ceiling=excluded.last_pay_ceiling, last_clears_floor=excluded.last_clears_floor",
            (key, p.get("source"), p.get("employer"), p.get("title"), p.get("url"),
             rec.get("first_seen") or today, today, rec.get("first_qualified"),
             1 if p.get("_qualifies_strict") else 0,
             p.get("pay_hourly"), p.get("pay_ceiling"), p.get("pay_clears_floor")))
    conn.commit()


def record_run(conn, summary):
    f = summary.get("funnel", {})
    pc = summary.get("pay_coverage", {})
    conn.execute(
        "INSERT OR REPLACE INTO runs(date, generated_at, fetched, rcm, ic_archetype, remote, "
        "  pay_ge30, offshore_resistant, qualifying, straddles, upper, net_new, pay_with, pay_unknown) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (summary.get("date"), summary.get("date"),
         f.get("0_total_fetched"), f.get("1_rcm_relevant"), f.get("2_ic_archetype"),
         f.get("3_fully_remote"), f.get("4_pay_ge_30"), f.get("5_offshore_resistant"),
         f.get("6_qualifying_strict"), summary.get("straddles_30_qualifying"),
         summary.get("pay_unknown_upper_bound_qualifying"),
         summary.get("net_new_qualifying_this_run"),
         pc.get("postings_with_posted_pay"), pc.get("postings_pay_unknown")))
    conn.commit()


def weekly_flow(conn, weeks=8):
    """Net-new qualifying per ISO week (the make-or-break flow signal), most recent first."""
    return [dict(r) for r in conn.execute(
        "SELECT strftime('%Y-W%W', first_qualified) AS week, COUNT(*) AS net_new "
        "FROM postings WHERE first_qualified IS NOT NULL "
        "GROUP BY week ORDER BY week DESC LIMIT ?", (weeks,))]


# ---------------------------------------------------------------------------
# P0-E applications
# ---------------------------------------------------------------------------
def add_application(conn, rec):
    nid = rec.get("id")
    if nid is None:
        nid = (conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM applications").fetchone()[0])
    conn.execute(
        "INSERT INTO applications(id, ts, user, employer, role, arm, callback, callback_date) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (nid, rec.get("ts"), rec.get("user"), rec.get("employer"), rec.get("role"),
         rec.get("arm"), None, None))
    conn.commit()
    return nid


def set_callback(conn, app_id, callback, when):
    cur = conn.execute("UPDATE applications SET callback=?, callback_date=? WHERE id=?",
                       (int(bool(callback)), when, app_id))
    conn.commit()
    return cur.rowcount


def list_applications(conn):
    out = []
    for r in conn.execute("SELECT * FROM applications ORDER BY id"):
        d = dict(r)
        d["callback"] = None if d["callback"] is None else bool(d["callback"])
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Crowdsourced pay reports (see scoring/pay_report.schema.json)
# ---------------------------------------------------------------------------
def add_pay_report(conn, r):
    conn.execute(
        "INSERT INTO pay_reports(canonical_role, geo, remote_mode, hourly, currency, "
        "  source_type, contributor_id, reported_at, consent, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (r["canonicalRole"], r["geo"], r["remoteMode"], r["hourly"], r.get("currency", "USD"),
         r["sourceType"], r["contributorId"], r["reportedAt"], int(bool(r.get("consent", True))),
         r.get("note")))
    conn.commit()


def pay_reports_for(conn, canonical_role, geo, remote_mode):
    """Reports for one (role x geo x mode) cell, shaped for pay.crowd_aggregate."""
    rows = conn.execute(
        "SELECT hourly, source_type AS sourceType, contributor_id AS contributorId, "
        "  reported_at AS reportedAt FROM pay_reports "
        "WHERE canonical_role=? AND geo=? AND remote_mode=? AND consent=1",
        (canonical_role, geo, remote_mode))
    return [dict(r) for r in rows]
