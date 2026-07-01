// Workday CXS adapter (TS). The SINGLE source of workdayContext() + CSRF + same-origin
// fetch — the content script imports these instead of re-implementing them (F6 kills the
// duplication). Endpoints captured live from devoted.wd1.myworkdayjobs.com.
import { jobPosting } from "../normalizer";
import type { JobPosting } from "../types";

export interface WorkdayCtx { tenant: string; site: string; origin: string; externalPath?: string | null; }

/** tenant/site/origin (+ externalPath on a job page) from a Workday careers URL. */
export function workdayContext(href: string): WorkdayCtx | null {
  try {
    const u = new URL(href);
    if (!/\.myworkdayjobs\.com$/.test(u.hostname)) return null;
    const tenant = u.hostname.split(".")[0];
    const parts = u.pathname.split("/").filter(Boolean); // [en-US, Site, job, ...]
    const site = parts[0] && /^[a-z]{2}-[A-Z]{2}$/.test(parts[0]) ? parts[1] : parts[0];
    const jobIdx = parts.indexOf("job");
    const externalPath = jobIdx >= 0 ? "/" + parts.slice(jobIdx + 1).join("/") : null;
    if (!tenant || !site) return null;
    return { tenant, site, origin: u.origin, externalPath };
  } catch { return null; }
}

/** CSRF token from the CALYPSO cookie — required by the CXS endpoints. */
export function csrfToken(): string {
  const m = (typeof document !== "undefined" ? document.cookie : "").match(/CALYPSO_CSRF_TOKEN=([^;]+)/);
  return m ? m[1] : "";
}

export function parseWorkdayList(json: any, ctx: Partial<WorkdayCtx> & { employer?: string } = {}): JobPosting[] {
  const { tenant, site, origin, employer } = ctx;
  return (json.jobPostings || []).map((j: any) => jobPosting({
    source: "workday",
    sourceId: (j.bulletFields && j.bulletFields[0]) || j.externalPath,
    employer: employer || tenant || "", title: j.title, location: j.locationsText,
    description: "",
    url: origin && site ? `${origin}/en-US/${site}${j.externalPath}` : j.externalPath,
    postedAt: j.postedOn || "",
  }));
}

export function parseWorkdayDetail(json: any, ctx: { employer?: string; origin?: string; site?: string } = {}): JobPosting {
  const i = json.jobPostingInfo || {};
  const url = ctx.origin && ctx.site && i.jobPostingId
    ? `${ctx.origin}/en-US/${ctx.site}/job/${i.jobPostingId}` : (i.externalUrl || "");
  return jobPosting({
    source: "workday", sourceId: i.jobReqId || i.jobPostingId || i.id,
    employer: ctx.employer || "", title: i.title, location: i.location || "",
    workplace: /remote/i.test(i.location || "") ? "remote" : "",
    description: i.jobDescription || "", url, postedAt: i.startDate || i.postedOn || "",
  });
}

// --- browser-only same-origin fetch (content-script context) --------------------
export async function fetchWorkdayJobs(ctx: WorkdayCtx, opts: { searchText?: string; limit?: number; offset?: number } = {}): Promise<JobPosting[]> {
  const { searchText = "", limit = 20, offset = 0 } = opts;
  const res = await fetch(`${ctx.origin}/wday/cxs/${ctx.tenant}/${ctx.site}/jobs`, {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json", "x-calypso-csrf-token": csrfToken() },
    body: JSON.stringify({ appliedFacets: {}, limit, offset, searchText }),
  });
  if (!res.ok) throw new Error(`workday jobs ${res.status}`);
  return parseWorkdayList(await res.json(), ctx);
}

export async function fetchWorkdayDetail(ctx: WorkdayCtx, externalPath: string, employer?: string): Promise<JobPosting> {
  const res = await fetch(`${ctx.origin}/wday/cxs/${ctx.tenant}/${ctx.site}/job${externalPath}`, {
    method: "GET", credentials: "include",
    headers: { Accept: "application/json", "x-calypso-csrf-token": csrfToken() },
  });
  if (!res.ok) throw new Error(`workday detail ${res.status}`);
  return parseWorkdayDetail(await res.json(), { employer, origin: ctx.origin, site: ctx.site });
}
