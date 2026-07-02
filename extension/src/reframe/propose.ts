// Proposer adapter. The LLM call needs a ZDR-enabled Anthropic key, which must
// NEVER be shipped in the extension. Instead the panel POSTs the resume + mode to
// a backend proxy the operator runs (holding the key, calling reframe.llm), and
// gets back the raw proposals. The client-side guard (guard.ts) then validates
// every proposal locally before anything is shown - so a compromised or hostile
// proxy still cannot make the panel display an ungrounded, fabricated edit.
import type { Edit } from "./types";

export interface ProposeConfig {
  endpoint: string; // e.g. https://your-proxy.example.com/reframe/propose
  targetTitle?: string;
}

export async function propose(
  resume: string,
  mode: string,
  cfg: ProposeConfig,
): Promise<Edit[]> {
  const res = await fetch(cfg.endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ resume, mode, target_title: cfg.targetTitle }),
  });
  if (!res.ok) throw new Error(`proposer proxy returned ${res.status}`);
  const data = (await res.json()) as { edits?: Edit[] };
  return Array.isArray(data.edits) ? data.edits : [];
}
