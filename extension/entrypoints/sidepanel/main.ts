// Side panel (WXT entrypoint, TS). Asks the content script for raw material, parses with
// the shared adapters, scores + estimates pay on-device, records extraction telemetry, and
// renders the trust verdicts. All extraction/scoring is client-side (score-don't-store).
import { scoreJob } from "../../src/score";
import { postedEstimate } from "../../src/pay";
import { parseWorkdayDetail } from "../../src/parsers/workday";
import { parseJsonLdBlocks } from "../../src/parsers/jsonld";
import { recordExtraction } from "../../src/telemetry";
import type { JobPosting, PayEstimate } from "../../src/types";
import { reviewProposals, renderReview, type Mode } from "../../src/reframe/review";
import { propose } from "../../src/reframe/propose";
import { SAMPLE_EDITS, SAMPLE_RESUME } from "../../src/reframe/sample";
import type { Edit } from "../../src/reframe/types";

const out = document.getElementById("out")!;
const empty = (msg: string) => { out.innerHTML = `<div class="empty">${msg}</div>`; };
const ESCAPE: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s: unknown) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESCAPE[c]);
const pill = (label: string, cls: string) => `<span class="pill ${cls}">${label}</span>`;

export function toPosting(raw: any): JobPosting | null {
  if (!raw || raw.kind === "none") return null;
  if (raw.kind === "workday-detail") return parseWorkdayDetail(raw.payload, { origin: raw.ctx?.origin, site: raw.ctx?.site });
  if (raw.kind === "jsonld") return parseJsonLdBlocks(raw.blocks, { url: raw.url });
  return null;
}

function payPill(pay: PayEstimate): string {
  const rnd = (x: number) => Math.round(x);
  const rng = pay.floorHourly == null ? ""
    : (pay.ceilingHourly != null && pay.ceilingHourly !== pay.floorHourly
      ? `$${rnd(pay.floorHourly)}–$${rnd(pay.ceilingHourly)}/hr` : `$${rnd(pay.floorHourly)}/hr`);
  if (pay.clearsFloor === "yes") return pill(rng, "ok");
  if (pay.clearsFloor === "straddles") return pill(`straddles $30 · ${rng}`, "mid");
  if (pay.clearsFloor === "no") return pill(`&lt; $30 · ${rng}`, "no");
  return pill("not posted", "mid");
}

export function render(p: JobPosting, target: HTMLElement = out): void {
  const pay = postedEstimate({ text: `${p.title || ""} ${p.description || ""}` });
  const pp: JobPosting = { ...p, payHourly: pay.floorHourly, payCeiling: pay.ceilingHourly };
  const s = scoreJob(pp);
  const v = (ok: unknown, mid: string, good: string, bad: string) =>
    ok === "remote" || ok === "accessible" || ok === true ? pill(good, "ok")
      : (ok === "unknown" || ok === "unclear" ? pill(mid, "mid") : pill(bad, "no"));
  target.innerHTML = `<div class="card">
    <div class="title">${esc(p.title) || "(untitled)"}</div>
    <div class="emp">${esc(p.employer)}${p.location ? " · " + esc(p.location) : ""}</div>
    <div class="verdict"><span>Accessible IC role</span>${v(s.roleArchetype, "", "yes", "no — leadership/other")}</div>
    <div class="verdict"><span>Fully remote</span>${v(s.remote, "unclear", "remote", "hybrid/onsite")}</div>
    <div class="verdict"><span>Pay ≥ $30/hr</span>${payPill(pay)}</div>
    <div class="verdict"><span>Offshore-resistant</span>${v(s.offshoreResistant, "", "yes", "at-risk")}</div>
    <div class="verdict"><span>Credential-accessible</span>${v(s.credential, "", "yes", s.credential)}</div>
    <div class="big">${s.qualifies ? pill("QUALIFIES — worth applying", "ok") : pill("Doesn’t fit the archetype", "no")}</div>
    ${s.reasons.length ? `<div class="reasons">Why: ${s.reasons.map(esc).join(" · ")}</div>` : ""}
  </div>`;
}

// --------------------------------------------------------------------------- //
// Re-Frame panel
// --------------------------------------------------------------------------- //
const rfOut = document.getElementById("rf-out")!;
const rfEmpty = (msg: string) => { rfOut.innerHTML = `<div class="empty">${esc(msg)}</div>`; };

function showReview(edits: Edit[], resume: string, mode: Mode): void {
  rfOut.innerHTML = renderReview(reviewProposals(edits, resume, mode));
}

function selectedMode(): Mode {
  return (document.getElementById("rf-mode") as HTMLSelectElement).value as Mode;
}

document.getElementById("rf-sample")?.addEventListener("click", () => {
  (document.getElementById("rf-resume") as HTMLTextAreaElement).value = SAMPLE_RESUME;
  showReview(SAMPLE_EDITS, SAMPLE_RESUME, selectedMode());
});

document.getElementById("rf-run")?.addEventListener("click", async () => {
  const resume = (document.getElementById("rf-resume") as HTMLTextAreaElement).value.trim();
  if (!resume) return rfEmpty("Paste your resume first.");
  const mode = selectedMode();
  if (mode === "control") return showReview([], resume, mode);

  rfEmpty("Getting suggestions…");
  try {
    const cfg = await chrome.storage?.local.get("reframe_proxy");
    const endpoint = cfg?.reframe_proxy as string | undefined;
    if (!endpoint) {
      return rfEmpty(
        "No proposer proxy configured. Set a `reframe_proxy` endpoint (a backend holding the ZDR key) — or click “Try sample” to see the on-device guard in action.",
      );
    }
    const edits = await propose(resume, mode, { endpoint });
    showReview(edits, resume, mode);
  } catch (e) {
    rfEmpty("Suggestion step failed: " + (e as Error).message);
  }
});

// --------------------------------------------------------------------------- //
// Tabs
// --------------------------------------------------------------------------- //
function activate(tab: "score" | "reframe"): void {
  document.getElementById("panel-score")!.hidden = tab !== "score";
  document.getElementById("panel-reframe")!.hidden = tab !== "reframe";
  document.getElementById("tab-score")!.classList.toggle("active", tab === "score");
  document.getElementById("tab-reframe")!.classList.toggle("active", tab === "reframe");
}
document.getElementById("tab-score")?.addEventListener("click", () => activate("score"));
document.getElementById("tab-reframe")?.addEventListener("click", () => activate("reframe"));

document.getElementById("scan")?.addEventListener("click", async () => {
  empty("Scoring…");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) return empty("No active tab.");
    const raw: any = await chrome.tabs.sendMessage(tab.id, { type: "UNTETHERED_EXTRACT" }).catch(() => null);
    if (!raw) return empty("Couldn’t reach this page (not a supported job board, or reload needed).");
    const adapter = raw.kind === "workday-detail" ? "workday" : raw.kind === "jsonld" ? "jsonld" : "none";
    const posting = toPosting(raw);
    if (!posting || !posting.title) {
      void recordExtraction(adapter, false, "no posting parsed");   // canary: couldn't parse
      return empty("Couldn’t parse a job posting on this page. (Honest “no score” beats a wrong one.)");
    }
    void recordExtraction(adapter, true);
    render(posting);
  } catch (e) {
    empty("Error: " + (e as Error).message);
  }
});
