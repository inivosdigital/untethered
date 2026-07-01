// Per-adapter extraction-success canaries + "couldn't parse" recording. The roadmap
// mandates these "from commit #1": silent mis-scoring is the #1 extension risk, so every
// parse attempt is recorded (success/failure) and the success rate is surfaced. The pure
// reducer (applyExtraction) is unit-tested; the chrome.storage wrapper is thin glue.
export interface AdapterStat { attempts: number; success: number; failures: number; lastFailure?: string; }
export type Telemetry = Record<string, AdapterStat>;

const KEY = "untethered.telemetry";

/** Pure reducer: fold one extraction outcome into the stats map (testable, no chrome). */
export function applyExtraction(t: Telemetry, adapter: string, ok: boolean, note = ""): Telemetry {
  const prev = t[adapter] || { attempts: 0, success: 0, failures: 0 };
  const s: AdapterStat = { ...prev, attempts: prev.attempts + 1 };
  if (ok) s.success += 1;
  else { s.failures += 1; s.lastFailure = note || "unparsed"; }
  return { ...t, [adapter]: s };
}

export function successRate(s: AdapterStat): number {
  return s.attempts ? s.success / s.attempts : 0;
}

export async function recordExtraction(adapter: string, ok: boolean, note = ""): Promise<void> {
  try {
    const cur = ((await chrome.storage?.local.get(KEY))?.[KEY] || {}) as Telemetry;
    await chrome.storage?.local.set({ [KEY]: applyExtraction(cur, adapter, ok, note) });
  } catch { /* telemetry is best-effort */ }
}

export async function extractionStats(): Promise<Telemetry> {
  try { return ((await chrome.storage?.local.get(KEY))?.[KEY] || {}) as Telemetry; }
  catch { return {}; }
}
