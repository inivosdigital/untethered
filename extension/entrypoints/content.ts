// Content script (WXT). Gathers raw material only — JSON-LD blocks, or (on Workday) the
// same-origin CXS detail JSON — and hands it to the side panel. NO DOM injection (the
// LinkedIn-detection mitigation). It imports workdayContext() + csrfToken() from the
// SHARED parser (src/parsers/workday.ts) instead of re-implementing them — the whole point
// of the F6 bundler migration.
import { workdayContext, csrfToken } from "../src/parsers/workday";

function ldJsonBlocks(): string[] {
  return Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
    .map((s) => s.textContent || "").filter(Boolean);
}

async function gather(): Promise<Record<string, unknown>> {
  const wd = workdayContext(location.href);
  if (wd && wd.externalPath) {
    try {
      const res = await fetch(`${wd.origin}/wday/cxs/${wd.tenant}/${wd.site}/job${wd.externalPath}`, {
        method: "GET", credentials: "include",
        headers: { Accept: "application/json", "x-calypso-csrf-token": csrfToken() },
      });
      if (res.ok) return { kind: "workday-detail", ctx: wd, payload: await res.json() };
    } catch { /* fall through to JSON-LD */ }
  }
  const blocks = ldJsonBlocks();
  if (blocks.length) return { kind: "jsonld", url: location.href, blocks };
  return { kind: "none", url: location.href };
}

export default defineContentScript({
  matches: [
    "https://*.myworkdayjobs.com/*", "https://boards.greenhouse.io/*",
    "https://*.greenhouse.io/*", "https://jobs.lever.co/*",
    "https://jobs.ashbyhq.com/*", "https://*.indeed.com/*",
  ],
  runAt: "document_idle",
  main() {
    chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
      if (msg && msg.type === "UNTETHERED_EXTRACT") {
        gather().then(sendResponse).catch((e) => sendResponse({ kind: "error", error: String(e) }));
        return true; // async response
      }
      return undefined;
    });
  },
});
