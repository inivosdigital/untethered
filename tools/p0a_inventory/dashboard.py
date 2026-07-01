#!/usr/bin/env python3
"""Untethered — P0 Command Center.

A zero-dependency (stdlib only) dashboard over the P0-A harvester's daily output
and the other Phase-0 validation spikes. It reads ``data/runs/*/summary.json`` and
the latest ``qualifying.csv`` LIVE on every request (no build step, always current)
and renders:

  * the make-or-break metric: net-new qualifying FLOW vs the single-digits/week KILL line
  * the 6-stage survival funnel (latest run)
  * a net-new-per-day flow trend (hand-rolled SVG, no chart lib)
  * pay coverage, source (board) counts, and the live qualifying-roles table
  * a Phase-0 spike tracker (P0-A live; P0-B/C/D/E read optional data/spikes/*.json)

Run:  python3 dashboard.py --out-dir ./data --port 8770 --host 0.0.0.0
Then open  http://<tailscale-ip>:8770/   (internal)  — served under pm2.
"""
import argparse
import csv
import glob
import json
import os
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT_DIR = "./data"

# GO/KILL thresholds straight from docs/BUILD_ROADMAP.md.
KILL_WEEKLY_FLOW = 10          # single digits/week nationally => KILL/PIVOT
KILL_STAGE1_SURVIVAL = 0.05    # <5-10% raw filter survival => feed framing dead

SPIKE_META = [
    {"id": "P0-A", "name": "Filtered live-inventory + freshness (free-feed half)",
     "make_or_break": True,
     "go": "Net-new qualifying refills fast enough to sustain recurring engagement.",
     "kill": "Net-new single digits/week nationally, or raw filter survival <5-10% -> pivot to staircase-first."},
    {"id": "P0-B", "name": "ATS-feed coverage test",
     "make_or_break": False,
     "go": "Coverage informs how much seed the owned feed can carry.",
     "kill": "<20-30% coverage -> owned feed is seed-only; the browser extension is load-bearing."},
    {"id": "P0-C", "name": "Extension parse spike (LinkedIn / Indeed / Workday)",
     "make_or_break": False,
     "go": "Field-extraction success high per adapter; LinkedIn no-injection stays undetected.",
     "kill": "JSON-LD absent in logged-in DOM or detection trips -> drop LinkedIn from V1."},
    {"id": "P0-D", "name": "OEWS / O*NET pay-engine accuracy",
     "make_or_break": False,
     "go": "Median abs error <=$3-5/hr, SOC mapping >=85%, separates $22 commodity from $34 specialist.",
     "kill": "Error >$5/hr or can't split the tiers -> crowdsourced real-pay must move into V1."},
    {"id": "P0-E", "name": "Resume-reframe callback A/B (the existential one)",
     "make_or_break": True,
     "go": "Statistically meaningful callback lift attributable to the reframe / title lever.",
     "kill": "Null or marginal lift -> redesign around segmentation + pay-truth, not the wedge."},
]


# ---------------------------------------------------------------------------
# Data aggregation (read live on every request)
# ---------------------------------------------------------------------------
def _load_runs(out_dir):
    runs = []
    for path in sorted(glob.glob(os.path.join(out_dir, "runs", "*", "summary.json"))):
        try:
            with open(path) as f:
                runs.append(json.load(f))
        except (ValueError, OSError):
            continue
    runs.sort(key=lambda r: r.get("date", ""))
    return runs


def _load_qualifying(out_dir, run_date):
    path = os.path.join(out_dir, "runs", run_date, "qualifying.csv")
    rows = []
    if not os.path.exists(path):
        return rows
    try:
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    except OSError:
        return rows
    # sort by pay desc (unknown last)
    def _pay(r):
        try:
            return float(r.get("pay_hourly") or 0)
        except ValueError:
            return 0.0
    rows.sort(key=_pay, reverse=True)
    return rows


def _load_spikes(out_dir):
    """Optional per-spike result files: data/spikes/*.json. Keyed by each file's own
    "id" field (e.g. "P0-D") so it matches the tracker regardless of filename."""
    out = {}
    for path in glob.glob(os.path.join(out_dir, "spikes", "*.json")):
        try:
            with open(path) as f:
                obj = json.load(f)
        except (ValueError, OSError):
            continue
        key = obj.get("id") or os.path.splitext(os.path.basename(path))[0].upper()
        out[key] = obj
    return out


def _days_between(a, b):
    try:
        return (datetime.fromisoformat(b).date() - datetime.fromisoformat(a).date()).days
    except ValueError:
        return None


def build_data(out_dir):
    runs = _load_runs(out_dir)
    latest = runs[-1] if runs else None
    latest_date = latest["date"] if latest else None

    # Per-day flow series. The FIRST run's net-new is baseline stock (every current
    # qualifier is "first seen qualifying" on day one), NOT flow — flag it so the
    # weekly-flow number isn't inflated by the seed.
    series = []
    for i, r in enumerate(runs):
        f = r.get("funnel", {})
        series.append({
            "date": r.get("date"),
            "net_new": r.get("net_new_qualifying_this_run", 0),
            "qualifying": f.get("6_qualifying_strict", 0),
            "upper": r.get("pay_unknown_upper_bound_qualifying", 0),
            "fetched": f.get("0_total_fetched", 0),
            "rcm": f.get("1_rcm_relevant", 0),
            "is_baseline": i == 0,
        })

    # Weekly flow = net-new over the last 7 days, EXCLUDING the baseline run.
    weekly_flow = 0
    if latest_date:
        for s in series:
            if s["is_baseline"]:
                continue
            d = _days_between(s["date"], latest_date)
            if d is not None and 0 <= d < 7:
                weekly_flow += s["net_new"]

    flow_runs = [s for s in series if not s["is_baseline"]]
    days_of_data = len(runs)
    stage1 = None
    if latest:
        f = latest["funnel"]
        tot = f.get("0_total_fetched", 0)
        stage1 = (f.get("1_rcm_relevant", 0) / tot) if tot else None

    # Honest verdict: too-early vs trending.
    if days_of_data < 14:
        verdict = {"state": "accumulating",
                   "text": f"ACCUMULATING — {days_of_data} day(s) of data. "
                           f"Flow needs ~4 weeks + P0-B/manual sampling before a GO/KILL call."}
    elif not flow_runs:
        verdict = {"state": "accumulating", "text": "ACCUMULATING — no post-baseline runs yet."}
    elif weekly_flow < KILL_WEEKLY_FLOW:
        verdict = {"state": "kill",
                   "text": f"KILL-ZONE — {weekly_flow} net-new/wk (< {KILL_WEEKLY_FLOW}). "
                           f"Free-feed flow is thin; lean on the staircase-first pivot."}
    else:
        verdict = {"state": "go",
                   "text": f"SUSTAINING — {weekly_flow} net-new/wk on the free feed (lower bound)."}

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "has_data": latest is not None,
        "latest": latest,
        "latest_date": latest_date,
        "days_of_data": days_of_data,
        "weekly_flow": weekly_flow,
        "stage1_survival": stage1,
        "verdict": verdict,
        "series": series,
        "flow_runs": flow_runs,
        "qualifying": _load_qualifying(out_dir, latest_date) if latest_date else [],
        "thresholds": {"kill_weekly_flow": KILL_WEEKLY_FLOW,
                       "kill_stage1_survival": KILL_STAGE1_SURVIVAL},
        "spikes_meta": SPIKE_META,
        "spikes_data": _load_spikes(out_dir),
    }


# ---------------------------------------------------------------------------
# HTTP handler  (HTML is static; all data comes from /api/data via fetch)
# ---------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Untethered — P0 Command Center</title>
<style>
  :root{
    --bg:#0b0f14; --panel:#131a22; --panel2:#0f151c; --line:#233040;
    --ink:#e6edf3; --dim:#8b98a5; --dimmer:#5b6672;
    --go:#3fb950; --kill:#f85149; --warn:#d29922; --accent:#58a6ff; --accent2:#bc8cff;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
  a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
  .wrap{max-width:1180px;margin:0 auto;padding:26px 22px 60px}
  header{display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:6px}
  h1{font-size:20px;margin:0;letter-spacing:.2px}
  h1 span{color:var(--dim);font-weight:400}
  .meta{color:var(--dimmer);font-size:12px}
  .caveat{background:linear-gradient(90deg,#2a1f0e,#1a1710);border:1px solid #3a2f14;
    color:#e8d9a8;border-radius:10px;padding:10px 14px;margin:14px 0 20px;font-size:12.5px}
  .grid{display:grid;gap:14px}
  .cols4{grid-template-columns:repeat(4,1fr)}
  .cols2{grid-template-columns:1.35fr 1fr}
  @media(max-width:880px){.cols4{grid-template-columns:repeat(2,1fr)}.cols2{grid-template-columns:1fr}}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
  .card h2{font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);margin:0 0 12px;font-weight:600}
  .kpi .n{font-size:30px;font-weight:700;line-height:1.1}
  .kpi .sub{color:var(--dim);font-size:12px;margin-top:3px}
  .hero{border-width:1px;position:relative;overflow:hidden}
  .hero .n{font-size:46px;font-weight:800}
  .badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:700;letter-spacing:.4px}
  .b-go{background:rgba(63,185,80,.15);color:var(--go);border:1px solid rgba(63,185,80,.4)}
  .b-kill{background:rgba(248,81,73,.15);color:var(--kill);border:1px solid rgba(248,81,73,.4)}
  .b-warn{background:rgba(210,153,34,.15);color:var(--warn);border:1px solid rgba(210,153,34,.4)}
  .b-dim{background:#1b2530;color:var(--dim);border:1px solid var(--line)}
  .funnel .row{display:flex;align-items:center;gap:10px;margin:7px 0}
  .funnel .lab{width:150px;color:var(--dim);font-size:12px;flex:none;text-align:right}
  .funnel .bar{height:22px;border-radius:5px;background:linear-gradient(90deg,var(--accent),var(--accent2));min-width:2px}
  .funnel .val{font-variant-numeric:tabular-nums;font-size:12.5px;color:var(--ink);flex:none;width:96px}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
  th{color:var(--dim);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
  td.pay{font-variant-numeric:tabular-nums;color:var(--go);font-weight:600;white-space:nowrap}
  tr:hover td{background:#0f161e}
  .spike{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}
  .spike:last-child{border-bottom:0}
  .spike .id{font-weight:700;font-size:13px;width:44px;flex:none}
  .spike-badge{flex:none;max-width:270px;text-align:right}
  .spike-badge .badge{white-space:normal;line-height:1.35;text-align:center;overflow-wrap:anywhere}
  .spike .body{flex:1} .spike .nm{font-weight:600;margin-bottom:2px}
  .spike .cri{color:var(--dimmer);font-size:11.5px}
  .flowchart{width:100%;height:180px}
  .axis{stroke:var(--line);stroke-width:1}
  .dim{color:var(--dim)} .mono{font-variant-numeric:tabular-nums}
  .foot{color:var(--dimmer);font-size:11.5px;margin-top:26px;border-top:1px solid var(--line);padding-top:14px}
  .empty{color:var(--dim);padding:40px;text-align:center}
</style></head>
<body><div class="wrap">
  <header>
    <h1>Untethered · <span>P0 Command Center</span></h1>
    <div class="meta" id="meta">loading…</div>
  </header>
  <div class="caveat" id="caveat"></div>
  <div id="app"><div class="empty">Loading…</div></div>
  <div class="foot" id="foot"></div>
</div>
<script>
const $ = (h) => { const t=document.createElement('template'); t.innerHTML=h.trim(); return t.content.firstChild; };
const num = (n) => (n==null?'—':n.toLocaleString());
const pct = (x) => (x==null?'—':(100*x).toFixed(1)+'%');
// escape untrusted feed strings (employer/title/url from qualifying.csv) before innerHTML
const esc = (s) => String(s==null?'':s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl = (u) => { u = String(u==null?'':u); return /^https?:\/\//i.test(u) ? u : ''; };

function funnelRows(f){
  const stages=[
    ['0 · fetched','0_total_fetched'],['1 · RCM-relevant','1_rcm_relevant'],
    ['2 · IC-archetype','2_ic_archetype'],['3 · fully-remote','3_fully_remote'],
    ['4 · pay ≥ $30/hr','4_pay_ge_30'],['5 · offshore-resistant','5_offshore_resistant'],
    ['6 · QUALIFYING','6_qualifying_strict']];
  const max=f['0_total_fetched']||1;
  return stages.map(([lab,k])=>{
    const v=f[k]||0, w=Math.max(2,(v/max)*100);
    return `<div class="row"><div class="lab">${lab}</div>
      <div class="bar" style="width:${w}%"></div>
      <div class="val">${num(v)} <span class="dim">(${pct(v/max)})</span></div></div>`;
  }).join('');
}

function flowSVG(runs){
  if(!runs.length) return '<div class="dim" style="padding:20px 0">No post-baseline runs yet — the flow trend starts on day 2.</div>';
  const W=560,H=180,pad=28, maxv=Math.max(10,...runs.map(r=>r.net_new));
  const bw=Math.min(46,(W-2*pad)/runs.length-8);
  const killY = H-pad-((10-1)/maxv)*(H-2*pad); // rough marker near single-digits line
  let bars='';
  runs.forEach((r,i)=>{
    const x=pad+i*((W-2*pad)/runs.length)+((W-2*pad)/runs.length-bw)/2;
    const h=Math.max(1,(r.net_new/maxv)*(H-2*pad)), y=H-pad-h;
    const col=r.net_new>=10?'var(--go)':'var(--warn)';
    bars+=`<rect x="${x}" y="${y}" width="${bw}" height="${h}" rx="3" fill="${col}"><title>${r.date}: ${r.net_new} net-new</title></rect>`;
    bars+=`<text x="${x+bw/2}" y="${H-pad+13}" fill="var(--dimmer)" font-size="9" text-anchor="middle">${r.date.slice(5)}</text>`;
    bars+=`<text x="${x+bw/2}" y="${y-4}" fill="var(--ink)" font-size="10" text-anchor="middle">${r.net_new}</text>`;
  });
  return `<svg class="flowchart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    <line class="axis" x1="${pad}" y1="${H-pad}" x2="${W-pad}" y2="${H-pad}"/>
    <line x1="${pad}" y1="${killY}" x2="${W-pad}" y2="${killY}" stroke="var(--kill)" stroke-dasharray="4 4" stroke-width="1"/>
    <text x="${W-pad}" y="${killY-4}" fill="var(--kill)" font-size="9" text-anchor="end">~KILL line (single digits/wk)</text>
    ${bars}</svg>`;
}

function render(d){
  document.getElementById('meta').textContent =
    `generated ${d.generated_at} · ${d.days_of_data} run(s) · latest ${d.latest_date||'—'}`;
  document.getElementById('caveat').innerHTML =
    '⚠ <b>LOWER BOUND.</b> Counts Greenhouse/Lever/Ashby'+
    (d.latest&&d.latest.sources&&d.latest.sources.usajobs_enabled?'+USAJOBS':'')+
    ' boards + '+((d.latest.sources.workday||[]).length)+' Workday tenants (pay-unknown — detail is browser-only; the extension supplies pay in-page). LinkedIn/Indeed/ZipRecruiter IC volume still NOT counted (see P0-B). Pay/offshore/credential/role filters are heuristics; spot-check qualifying.csv.';

  const app=document.getElementById('app');
  if(!d.has_data){ app.innerHTML='<div class="card empty">No harvest runs yet. The daily pm2 job <code>p0a-harvest</code> writes data/runs/&lt;date&gt;/ at 09:00.</div>'; return; }

  const f=d.latest.funnel, v=d.verdict;
  const bcls={go:'b-go',kill:'b-kill',accumulating:'b-warn'}[v.state]||'b-dim';
  const pc=d.latest.pay_coverage||{}, src=d.latest.sources||{};
  const nBoards=(src.greenhouse||[]).length+(src.lever||[]).length+(src.ashby||[]).length+(src.workday||[]).length;

  app.innerHTML='';
  // Row 1 — hero + KPIs
  app.appendChild($(`<div class="grid cols4" style="margin-bottom:14px">
    <div class="card hero" style="grid-column:span 2">
      <h2>Make-or-break · net-new qualifying flow</h2>
      <div class="n">${num(d.weekly_flow)}<span class="dim" style="font-size:16px;font-weight:500">/wk</span></div>
      <div class="sub" style="margin:6px 0 10px">post-baseline net-new over the last 7 days · KILL line &lt; ${d.thresholds.kill_weekly_flow}/wk</div>
      <span class="badge ${bcls}">${v.text}</span>
    </div>
    <div class="card kpi"><h2>Qualifying (stock)</h2>
      <div class="n">${num(f['6_qualifying_strict'])}</div>
      <div class="sub">strict · ${num(d.latest.straddles_30_qualifying||0)} straddle $30 · ${num(d.latest.pay_unknown_upper_bound_qualifying)} upper</div></div>
    <div class="card kpi"><h2>Stage-1 survival</h2>
      <div class="n">${pct(d.stage1_survival)}</div>
      <div class="sub">RCM-relevant / fetched · KILL &lt; 5–10%</div></div>
  </div>`));

  // Row 2 — funnel + flow chart
  app.appendChild($(`<div class="grid cols2" style="margin-bottom:14px">
    <div class="card funnel"><h2>Survival funnel · ${d.latest_date}</h2>${funnelRows(f)}</div>
    <div class="card"><h2>Net-new per day (flow)</h2>${flowSVG(d.flow_runs)}
      <div class="sub dim" style="margin-top:6px">Day-1 is the baseline seed (full stock), excluded from weekly flow.</div></div>
  </div>`));

  // Row 3 — pay coverage + sources + qualifying table
  const cov=pc.postings_with_posted_pay||0, tot=(pc.postings_with_posted_pay||0)+(pc.postings_pay_unknown||0);
  app.appendChild($(`<div class="grid cols4" style="margin-bottom:14px">
    <div class="card kpi"><h2>Pay coverage</h2><div class="n">${tot?Math.round(100*cov/tot):0}%</div>
      <div class="sub">${num(cov)}/${num(tot)} have posted pay</div></div>
    <div class="card kpi"><h2>Boards seeded</h2><div class="n">${num(nBoards)}</div>
      <div class="sub">GH ${(src.greenhouse||[]).length} · Lv ${(src.lever||[]).length} · Ab ${(src.ashby||[]).length} · Wd ${(src.workday||[]).length}</div></div>
    <div class="card kpi"><h2>Fetched today</h2><div class="n">${num(f['0_total_fetched'])}</div>
      <div class="sub">${num(f['1_rcm_relevant'])} RCM · ${num(f['2_ic_archetype'])} IC-archetype</div></div>
    <div class="card kpi"><h2>Offshore-resistant</h2><div class="n">${num(f['5_offshore_resistant'])}</div>
      <div class="sub">remote+pay+resistant, pre-credential</div></div>
  </div>`));

  // Qualifying roles
  const q=d.qualifying||[];
  const rows=q.map(r=>`<tr><td>${esc(r.employer)}</td><td>${esc(r.title)}</td>
    <td class="pay">${r.pay_hourly?('$'+(+r.pay_hourly).toFixed(0)+'/hr'):'—'}</td>
    <td class="dim mono">${esc(r.source)}</td>
    <td>${safeUrl(r.url)?`<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener">open ↗</a>`:''}</td></tr>`).join('');
  app.appendChild($(`<div class="card" style="margin-bottom:14px"><h2>Qualifying roles · ${q.length} (spot-check these)</h2>
    <div style="overflow:auto"><table><thead><tr><th>Employer</th><th>Title</th><th>Pay</th><th>Src</th><th></th></tr></thead>
    <tbody>${rows||'<tr><td colspan=5 class="dim">none this run</td></tr>'}</tbody></table></div></div>`));

  // Phase-0 spike tracker
  const spikes=d.spikes_meta.map(s=>{
    const res=d.spikes_data[s.id];
    let badge=`<span class="badge b-dim">not started</span>`;
    if(s.id==='P0-A'){ badge=`<span class="badge ${bcls}">${v.state.toUpperCase()}</span>`; }
    else if(res){ const st=(res.status||'done'); const cl=st==='go'?'b-go':st==='kill'?'b-kill':'b-warn';
      badge=`<span class="badge ${cl}">${(res.headline||st).toString().slice(0,120)}</span>`; }
    return `<div class="spike"><div class="id">${s.id}</div><div class="body">
      <div class="nm">${s.name} ${s.make_or_break?'<span class="badge b-dim" style="font-size:9px">make-or-break</span>':''}</div>
      <div class="cri"><b>GO:</b> ${s.go}<br><b>KILL:</b> ${s.kill}</div></div>
      <div class="spike-badge">${badge}</div></div>`;
  }).join('');
  app.appendChild($(`<div class="card"><h2>Phase-0 validation tracker</h2>${spikes}</div>`));

  document.getElementById('foot').innerHTML =
    'Reads tools/p0a_inventory/data/runs/*/summary.json live · P0-B/D results drop into data/spikes/*.json as they land · '+
    'GO/KILL thresholds from docs/BUILD_ROADMAP.md.';
}

fetch('/api/data').then(r=>r.json()).then(render).catch(e=>{
  document.getElementById('app').innerHTML='<div class="card empty">Failed to load data: '+e+'</div>';
});
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    out_dir = OUT_DIR

    def _send(self, code, body, ctype):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/data"):
            try:
                payload = json.dumps(build_data(self.out_dir))
            except Exception as e:  # noqa: BLE001 — never 500 the dashboard
                payload = json.dumps({"has_data": False, "error": str(e)})
            return self._send(200, payload, "application/json")
        if self.path in ("/favicon.ico",):
            return self._send(204, b"", "image/x-icon")
        return self._send(200, PAGE, "text/html; charset=utf-8")

    def log_message(self, *a):  # quiet; pm2 captures stdout
        pass


def main():
    ap = argparse.ArgumentParser(description="Untethered P0 command center")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="0.0.0.0")
    args = ap.parse_args()
    Handler.out_dir = args.out_dir
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"P0 command center on http://{args.host}:{args.port}/  (out-dir={args.out_dir})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
