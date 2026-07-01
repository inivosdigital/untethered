// Remote-config site/adapter map (DATA, not code). The bundled DEFAULT_ADAPTERS are the
// fallback; a fetched override lives in chrome.storage so a selector/host change ships
// WITHOUT a Chrome Web Store round-trip (MV3 bans remote CODE, but remote DATA is allowed).
export type AdapterKind = "workday" | "jsonld";
export interface SiteAdapter { id: string; hostPattern: string; kind: AdapterKind; note?: string; }

export const DEFAULT_ADAPTERS: SiteAdapter[] = [
  { id: "workday", hostPattern: "\\.myworkdayjobs\\.com$", kind: "workday",
    note: "CXS API (same-origin content-script fetch). Beachhead surface (P0-B)." },
  { id: "greenhouse", hostPattern: "(^|\\.)(greenhouse\\.io|boards\\.greenhouse\\.io)$", kind: "jsonld" },
  { id: "lever", hostPattern: "(^|\\.)lever\\.co$", kind: "jsonld" },
  { id: "ashby", hostPattern: "(^|\\.)ashbyhq\\.com$", kind: "jsonld" },
  { id: "indeed", hostPattern: "(^|\\.)indeed\\.com$", kind: "jsonld",
    note: "Cloudflare/Turnstile interstitials -> skip-and-retry (P0-C)." },
  // linkedin: DEFERRED behind the detection canary (P0-C) — not in content_scripts.
];

const STORAGE_KEY = "untethered.adapters";

export function adapterFor(hostname: string, adapters: SiteAdapter[] = DEFAULT_ADAPTERS): SiteAdapter | null {
  return adapters.find((a) => new RegExp(a.hostPattern, "i").test(hostname)) || null;
}

/** Load adapters: chrome.storage override if present, else the bundled defaults. */
export async function loadAdapters(): Promise<SiteAdapter[]> {
  try {
    const got = await chrome.storage?.local.get(STORAGE_KEY);
    const remote = got?.[STORAGE_KEY];
    if (Array.isArray(remote) && remote.length) return remote as SiteAdapter[];
  } catch { /* fall through to defaults */ }
  return DEFAULT_ADAPTERS;
}

/** Refresh the adapter map from a remote JSON URL (DATA only) into chrome.storage. */
export async function refreshAdaptersFromRemote(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { credentials: "omit" });
    if (!res.ok) return false;
    const data = await res.json();
    if (!Array.isArray(data) || !data.every((a) => a && a.hostPattern && a.kind)) return false;
    await chrome.storage?.local.set({ [STORAGE_KEY]: data });
    return true;
  } catch { return false; }
}
