// Client-side scoring engine (ported to TS for F6). Rules from the canonical rules.json;
// parity with the Python harvester is guarded by scoring/parity_fixtures.json.
import rulesJson from "./scoring/rules.json";
import type { Rules, JobPosting, ScoreResult } from "./types";
import { clearsFloor } from "./pay";

const RULES = rulesJson as Rules;
export const FLOOR_HOURLY = RULES.floor_hourly;

const TITLE_KEYWORDS = RULES.title_keywords.map((k) => k.toLowerCase());
const ONSHORE = RULES.onshore_signals;
const OFFSHORE = RULES.offshore_signals;

const rx = (name: string) => new RegExp(RULES.regex[name], "i");
const RN_GATE = rx("rn_gate");
const DEGREE_GATE = rx("degree_gate");
const HYBRID = rx("hybrid_flags");
const REMOTE = rx("remote_flags");
const NEG_REMOTE = rx("neg_remote_flags");
const REMOTE_ANYWHERE = rx("remote_anywhere_flags");
const SENIORITY = rx("seniority_exclude");
const FUNCTION_EX = rx("function_exclude");
const LEADER = rx("leader_exclude");
const LEADER_KEEP = rx("leader_keep");

type P = Pick<JobPosting, "title" | "description" | "workplace" | "location" | "payHourly" | "payCeiling">;

function signalHits(text: string, signals: string[]): number {
  return signals.reduce((n, s) =>
    n + (new RegExp("\\b" + s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(text) ? 1 : 0), 0);
}

export function fRcm(p: P, kw = TITLE_KEYWORDS): boolean {
  const hay = `${p.title} ${p.description.slice(0, 400)}`.toLowerCase();
  return kw.some((k) => hay.includes(k));
}

export function fRoleArchetype(p: P): boolean {
  const t = p.title || "";
  if (SENIORITY.test(t) || FUNCTION_EX.test(t)) return false;
  if (LEADER.test(t) && !LEADER_KEEP.test(t)) return false;
  return true;
}

export function fRemote(p: P): ScoreResult["remote"] {
  const blob = `${p.workplace} ${p.location} ${p.description}`;
  const wp = (p.workplace || "").toLowerCase();
  if (NEG_REMOTE.test(blob)) return "hybrid_or_onsite";
  if (["on-site", "onsite", "hybrid"].includes(wp)) return "hybrid_or_onsite";
  if (HYBRID.test(blob) && !REMOTE_ANYWHERE.test(blob)) return "hybrid_or_onsite";
  if (wp === "remote" || REMOTE.test(blob)) return "remote";
  return "unclear";
}

export function fPay(p: P): ScoreResult["pay"] {
  const map = { yes: "ge30", no: "lt30", straddles: "straddles", unknown: "unknown" } as const;
  return map[clearsFloor(p.payHourly, p.payCeiling)];
}

export function fOffshoreResistant(p: P): { resistant: boolean; on: number; off: number } {
  const text = `${p.title} ${p.description}`.toLowerCase();
  const on = signalHits(text, ONSHORE), off = signalHits(text, OFFSHORE);
  return { resistant: on >= 1 && on >= off, on, off };
}

export function fCredential(p: P): ScoreResult["credential"] {
  const text = `${p.title} ${p.description}`;
  if (RN_GATE.test(text)) return "rn_gated";
  if (DEGREE_GATE.test(text)) return "degree_gated";
  return "accessible";
}

export function scoreJob(p: P): ScoreResult {
  const rcm = fRcm(p);
  const roleArchetype = fRoleArchetype(p);
  const remote = fRemote(p);
  const pay = fPay(p);
  const { resistant, on, off } = fOffshoreResistant(p);
  const credential = fCredential(p);
  const qualifies = rcm && roleArchetype && remote === "remote" && pay === "ge30"
    && resistant && credential === "accessible";
  const reasons: string[] = [];
  if (!rcm) reasons.push("not an RCM-relevant title");
  if (!roleArchetype) reasons.push("leadership / wrong-function / clinical title");
  if (remote !== "remote") reasons.push(`remote: ${remote}`);
  if (pay !== "ge30") reasons.push(`pay: ${pay}`);
  if (!resistant) reasons.push(`offshore-prone (on ${on}/off ${off})`);
  if (credential !== "accessible") reasons.push(credential);
  return { rcm, roleArchetype, remote, pay, offshoreResistant: resistant,
    onshoreScore: on, offshoreScore: off, credential, qualifies, reasons };
}
