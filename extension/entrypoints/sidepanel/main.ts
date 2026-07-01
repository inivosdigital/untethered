// Side panel (WXT entrypoint, TS). Asks the content script for raw material, parses with
// the shared adapters, scores + estimates pay on-device, records extraction telemetry, and
// renders the trust verdicts. All extraction/scoring is client-side (score-don't-store).
import { scoreJob } from "../../src/score";
import { postedEstimate } from "../../src/pay";
import { parseWorkdayDetail } from "../../src/parsers/workday";
import { parseJsonLdBlocks } from "../../src/parsers/jsonld";
import { recordExtraction } from "../../src/telemetry";
import type { JobPosting, PayEstimate } from "../../src/types";

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
