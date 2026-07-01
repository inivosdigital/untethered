// Unit normalization — single source of `toHourly`, shared by normalizer.ts and pay.ts.
// Mirrors tools/p0a_inventory/scoring_rules.py:to_hourly (constants + interval codes from
// the canonical rules.json).
import rulesJson from "./scoring/rules.json";
import type { Rules } from "./types";

const RULES = rulesJson as Rules;
const HPY = RULES.hours_per_year;
const HPD = RULES.hours_per_day;
const CODES = RULES.interval_codes;

export const HOURS_PER_YEAR = HPY;
export const HOURS_PER_DAY = HPD;

/** Normalize an amount + interval hint to $/hr. Handles English words and bare USAJOBS
 *  codes ('ph'/'pa'/'bw'); magnitude fallback for unknown hints. */
export function toHourly(amount: number | null | undefined, hint = ""): number | null {
  if (amount == null || isNaN(amount)) return null;
  let h = String(hint).toLowerCase().trim();
  h = CODES[h] ?? h;
  if (/hour|hr|\/h/.test(h)) return amount;
  if (/year|annual|annum|yr|\/y/.test(h)) return amount / HPY;
  if (/bi[-\s]?week/.test(h)) return (amount * 26) / HPY;
  if (/month|\/mo|mth/.test(h)) return (amount * 12) / HPY;
  if (/week|wk/.test(h)) return (amount * 52) / HPY;
  if (/day|daily|diem/.test(h)) return amount / HPD;
  return amount < 1000 ? amount : amount / HPY;
}
