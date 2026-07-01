// Canonical JobPosting shape + text helpers (ported to TS for F6).
import { postedEstimate } from "./pay";
import type { JobPosting, StructuredPay } from "./types";
export { toHourly, HOURS_PER_YEAR, HOURS_PER_DAY } from "./units";

/** Strip HTML tags/entities to plain text (mirrors harvest.py strip_html). */
export function stripHtml(raw: string): string {
  if (!raw) return "";
  let t = String(raw)
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&")
    .replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&nbsp;/g, " ");
  t = t.replace(/<[^>]+>/g, " ");
  return t.replace(/\s+/g, " ").trim();
}

/** Legacy helper (returns just the floor). Kept for tests; delegates to the pay engine. */
export function parsePayFromText(text: string): { hourly: number | null; raw: string | null } {
  const est = postedEstimate({ text });
  return { hourly: est.floorHourly, raw: est.source === "none" ? null : est.note || null };
}

/** Build the canonical record. Pay is a full PayEstimate (floor + ceiling), so scoring and
 *  the side panel are straddle-aware without per-adapter pay quirks. */
export function jobPosting(args: {
  source: string; sourceId: string | number | null | undefined; employer?: string;
  title?: string; location?: string; workplace?: string; description?: string;
  structured?: StructuredPay | null; url?: string; postedAt?: string;
}): JobPosting {
  const { source, sourceId, employer, title, location, workplace = "",
    description = "", structured = null, url = "", postedAt = "" } = args;
  const desc = stripHtml(description);
  const est = postedEstimate({ structured: structured || undefined, text: `${title || ""} ${desc}` });
  return {
    source, sourceId: String(sourceId ?? ""), employer: employer || "",
    title: title || "", location: location || "", workplace: workplace || "",
    description: desc, payHourly: est.floorHourly, payCeiling: est.ceilingHourly,
    paySource: est.source === "none" ? "" : `${est.source}:${est.confidence}`,
    url: url || "", postedAt: postedAt || "",
  };
}
