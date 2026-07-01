// JSON-LD-first adapter (TS). Emits a canonical JobPosting with STRUCTURED pay (min/max/
// currency/period) so the pay engine decides the floor/straddle — no per-adapter pay math.
import { jobPosting } from "../normalizer";
import type { JobPosting, StructuredPay } from "../types";

type Node = Record<string, any>;

function firstJobPosting(node: any, seen = new Set<any>()): Node | null {
  if (!node || typeof node !== "object" || seen.has(node)) return null;
  seen.add(node);
  const type = node["@type"];
  const isJob = type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"));
  if (isJob) return node;
  for (const v of Object.values(node)) {
    if (Array.isArray(v)) {
      for (const x of v) { const r = firstJobPosting(x, seen); if (r) return r; }
    } else if (v && typeof v === "object") {
      const r = firstJobPosting(v, seen); if (r) return r;
    }
  }
  return null;
}

function structuredFromSalary(baseSalary: any): StructuredPay | null {
  if (!baseSalary || typeof baseSalary !== "object") return null;
  const v = baseSalary.value || baseSalary;
  const min = v.minValue ?? v.value;
  const max = v.maxValue ?? v.value;
  if (min == null && max == null) return null;
  // missing unitText -> "" so the pay engine magnitude-guesses (small=hourly, large=annual)
  // instead of assuming annual and mis-scaling a $45/hr value to $0.02/hr.
  return { min, max, currency: baseSalary.currency || v.currency || "USD", interval: v.unitText || "" };
}

function locationText(node: Node): string {
  const loc = node.jobLocation;
  const one = Array.isArray(loc) ? loc[0] : loc;
  const addr = one && one.address;
  if (addr) return [addr.addressLocality, addr.addressRegion].filter(Boolean).join(", ") || addr.addressCountry || "";
  const remoteReq = node.applicantLocationRequirements;
  if (remoteReq) return (Array.isArray(remoteReq) ? remoteReq[0] : remoteReq).name || "";
  return "";
}

export function parseJsonLdObject(obj: any, { url = "" }: { url?: string } = {}): JobPosting | null {
  const j = firstJobPosting(obj);
  if (!j) return null;
  const org = j.hiringOrganization;
  const jlt = j.jobLocationType;
  const workplace = jlt === "TELECOMMUTE" || (Array.isArray(jlt) && jlt.includes("TELECOMMUTE")) ? "remote" : "";
  return jobPosting({
    source: "jsonld",
    sourceId: j.identifier?.value || j.identifier || j.url || url,
    employer: (org && (org.name || org)) || "",
    title: j.title, location: locationText(j), workplace,
    description: j.description || "", structured: structuredFromSalary(j.baseSalary),
    url: j.url || url, postedAt: j.datePosted || "",
  });
}

export function parseJsonLdBlocks(blocks: string[], ctx: { url?: string } = {}): JobPosting | null {
  for (const raw of blocks) {
    let data: any;
    try { data = JSON.parse(raw); } catch { continue; }
    const nodes = Array.isArray(data) ? data : [data];
    for (const n of nodes) {
      const p = parseJsonLdObject(n, ctx);
      if (p) return p;
    }
  }
  return null;
}
