// Shared types for the Untethered extension (F6). One JobPosting, one PayEstimate,
// one ScoreResult — consumed by the content script, side panel, and service worker via
// the bundler, so no context re-implements them.

export interface Rules {
  version: number;
  floor_hourly: number;
  hours_per_year: number;
  hours_per_day: number;
  title_keywords: string[];
  onshore_signals: string[];
  offshore_signals: string[];
  pay_disqualifiers: string[];
  interval_codes: Record<string, string>;
  regex: Record<string, string>;
}

export interface JobPosting {
  source: string;
  sourceId: string;
  employer: string;
  title: string;
  location: string;
  workplace: string;
  description: string;
  payHourly: number | null;
  payCeiling?: number | null;
  paySource: string;
  url: string;
  postedAt: string;
}

export type ClearsFloor = "yes" | "no" | "straddles" | "unknown";

export interface PayEstimate {
  floorHourly: number | null;
  ceilingHourly: number | null;
  currency: string;
  period: string;
  source: "posted" | "crowdsourced" | "oews-prior" | "none";
  confidence: "high" | "medium" | "low" | "abstain";
  clearsFloor: ClearsFloor;
  straddlesFloor: boolean;
  note: string;
}

export interface PayRange {
  minHourly: number;
  maxHourly: number;
  currency: string;
  period: string;
  basis: "structured" | "text" | "text-single";
}

export interface StructuredPay {
  min?: number | string | null;
  max?: number | string | null;
  currency?: string | null;
  interval?: string | null;
}

export interface ScoreResult {
  rcm: boolean;
  roleArchetype: boolean;
  remote: "remote" | "hybrid_or_onsite" | "unclear";
  pay: "ge30" | "lt30" | "straddles" | "unknown";
  offshoreResistant: boolean;
  onshoreScore: number;
  offshoreScore: number;
  credential: "accessible" | "rn_gated" | "degree_gated";
  qualifies: boolean;
  reasons: string[];
}

export interface PayReport {
  hourly: number;
  contributorId: string;
  sourceType?: string;
  reportedAt: string;
}
