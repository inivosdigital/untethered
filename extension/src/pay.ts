// Pay-truth engine (F2, ported to TS for F6). Mirrors tools/p0a_inventory/pay.py; parity
// guarded by scoring/pay_parity_fixtures.json. Floor = LOWER bound (+ explicit "straddles
// $30"); OEWS prior ABSTAINS.
import rulesJson from "./scoring/rules.json";
import type { Rules, PayEstimate, PayRange, StructuredPay, ClearsFloor, PayReport } from "./types";
import { toHourly } from "./units";

const RULES = rulesJson as Rules;
export const FLOOR_HOURLY = RULES.floor_hourly;
const DISQ = RULES.pay_disqualifiers;
const HOURLY_RX = new RegExp(RULES.regex.pay_hourly, "i");
const RANGE_RX = new RegExp(RULES.regex.pay_range, "i");

const num = (s: unknown): number => parseFloat(String(s).replace(/,/g, ""));
const r2 = (x: number | null): number | null => (x == null ? null : Math.round(x * 100) / 100);

function nearDisqualifier(low: string, start: number, len: number): boolean {
  const ctx = low.slice(Math.max(0, start - 28), start + len + 28);
  return DISQ.some((b) => ctx.includes(b));
}

export function clearsFloor(floor: number | null | undefined, ceiling?: number | null): ClearsFloor {
  if (floor == null) return "unknown";
  if (floor >= FLOOR_HOURLY) return "yes";
  if (ceiling != null && ceiling >= FLOOR_HOURLY) return "straddles";
  return "no";
}

const NONE: PayEstimate = {
  floorHourly: null, ceilingHourly: null, currency: "USD", period: "",
  source: "none", confidence: "abstain", clearsFloor: "unknown",
  straddlesFloor: false, note: "no pay signal",
};

export function rangeFromStructured({ min, max, currency, interval }: StructuredPay = {}): PayRange | null {
  if ((currency || "USD").toUpperCase() !== "USD") return null;
  const conv = (v: number | string | null | undefined): number | null => {
    const n = num(v);
    return isNaN(n) ? null : toHourly(n, interval || "");
  };
  const lo = min != null ? conv(min) : null;
  const hi = max != null ? conv(max) : null;
  if (lo == null && hi == null) return null;
  return { minHourly: (lo ?? hi)!, maxHourly: (hi ?? lo)!, currency: "USD",
    period: interval || "", basis: "structured" };
}

export function rangeFromText(text: string): PayRange | null {
  if (!text) return null;
  const h = text.match(HOURLY_RX);
  if (h) {
    const lo = parseFloat(h[1]); const hi = h[2] ? parseFloat(h[2]) : lo;
    return { minHourly: Math.min(lo, hi), maxHourly: Math.max(lo, hi),
      currency: "USD", period: "hour", basis: "text" };
  }
  const low = text.toLowerCase();
  const r = text.match(RANGE_RX);
  if (r && r.index != null && !nearDisqualifier(low, r.index, r[0].length)) {
    const a2 = num(r[1]), b2 = num(r[2]);
    const lo2 = Math.min(a2, b2);
    if (lo2 >= 10 && Math.max(a2, b2) / lo2 <= 25) {
      const period = lo2 > 1500 ? "year" : "hour";
      return { minHourly: toHourly(lo2, period)!, maxHourly: toHourly(Math.max(a2, b2), period)!,
        currency: "USD", period, basis: "text" };
    }
  }
  const money = new RegExp(RULES.regex.money, "g");
  const nums: number[] = [];
  let m: RegExpExecArray | null;
  while ((m = money.exec(text)) !== null) {
    if (nearDisqualifier(low, m.index, m[0].length)) continue;
    const v = num(m[1]); if (v >= 10) nums.push(v);
  }
  if (!nums.length) return null;
  const top = Math.max(...nums);
  const period = top > 1500 ? "year" : "hour";
  const hourly = toHourly(top, period)!;
  return { minHourly: hourly, maxHourly: hourly, currency: "USD", period, basis: "text-single" };
}

function fromRange(range: PayRange | null, source: PayEstimate["source"]): PayEstimate {
  if (!range) return { ...NONE };
  const floor = r2(range.minHourly), ceiling = r2(range.maxHourly);
  const cf = clearsFloor(floor, ceiling);
  const confidence: PayEstimate["confidence"] =
    range.basis === "structured" ? "high" : range.basis === "text" ? "medium" : "low";
  return { floorHourly: floor, ceilingHourly: ceiling, currency: range.currency || "USD",
    period: range.period || "", source, confidence, clearsFloor: cf,
    straddlesFloor: cf === "straddles",
    note: cf === "straddles" ? "posted range straddles $30 — floor below, ceiling above" : "" };
}

export function postedEstimate({ structured, text }: { structured?: StructuredPay; text?: string } = {}): PayEstimate {
  const range = rangeFromStructured(structured || {}) || rangeFromText(text || "");
  return fromRange(range, "posted");
}

export function oewsPrior({ p25, p75 }: { p25?: number | null; p75?: number | null } = {}): PayEstimate {
  if (p25 == null && p75 == null) return { ...NONE };
  return { floorHourly: r2(p25 ?? null), ceilingHourly: r2(p75 ?? null), currency: "USD",
    period: "hour", source: "oews-prior", confidence: "abstain", clearsFloor: "unknown",
    straddlesFloor: false, note: "OEWS p25-p75 band (context only; abstains from a floor verdict)" };
}

export function crowdAggregate(
  reports: PayReport[],
  opts: { minContributors?: number; minMonths?: number; maxSourceShare?: number } = {},
): PayEstimate | null {
  const { minContributors = 5, minMonths = 3, maxSourceShare = 0.25 } = opts;
  if (!Array.isArray(reports)) return null;
  const valid = reports.filter((r) => r && typeof r.hourly === "number" && r.contributorId);
  if (new Set(valid.map((r) => r.contributorId)).size < minContributors) return null;
  const times = valid.map((r) => Date.parse(r.reportedAt)).filter((t) => !Number.isNaN(t));
  if (times.length) {
    const spanMonths = (Math.max(...times) - Math.min(...times)) / (1000 * 60 * 60 * 24 * 30.44);
    if (spanMonths < minMonths) return null;
  } else if (minMonths > 0) return null;
  const bySource: Record<string, number> = {};
  for (const r of valid) bySource[r.sourceType || "unknown"] = (bySource[r.sourceType || "unknown"] || 0) + 1;
  if (Math.max(...Object.values(bySource)) / valid.length > maxSourceShare) return null;
  const sorted = valid.map((r) => r.hourly).sort((a, b) => a - b);
  const q = (p: number) => sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];
  const floor = r2(q(0.25)), ceiling = r2(q(0.75));
  const cf = clearsFloor(floor, ceiling);
  return { floorHourly: floor, ceilingHourly: ceiling, currency: "USD", period: "hour",
    source: "crowdsourced", confidence: sorted.length >= 30 ? "high" : "medium",
    clearsFloor: cf, straddlesFloor: cf === "straddles",
    note: `crowdsourced p25-p75 from ${sorted.length} reports` };
}

export function combine({ posted, crowd, oews }: { posted?: PayEstimate; crowd?: PayEstimate | null; oews?: PayEstimate } = {}): PayEstimate {
  for (const e of [posted, crowd, oews]) if (e && e.source !== "none") return e;
  return { ...NONE };
}
