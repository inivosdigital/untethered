// Vocabulary + entity extraction for the client-side fabrication guard.
// EXACT TypeScript mirror of reframe/taxonomy.py; cross-language parity is
// guarded by scoring/reframe_guard_parity_fixtures.json. The recruiter-search
// taxonomy comes from the canonical scoring/rules.json (title_keywords); the RCM
// claim vocabulary from lexicon.json (a byte-identical copy of reframe/lexicon.json).
import rulesJson from "../scoring/rules.json";
import lexiconJson from "./lexicon.json";
import type { Lexicon } from "./types";

const RULES = rulesJson as { title_keywords: string[] };
const LEX = lexiconJson as Lexicon;

export const TARGET_TITLES = RULES.title_keywords.map((t) => t.toLowerCase());

// Deterministic (-len, then alpha) so entity ordering matches the Python guard.
const CLAIM_TERMS = Array.from(
  new Set(
    [...LEX.certs, ...LEX.systems, ...LEX.clearinghouses, ...LEX.insurers, ...LEX.codesets].map(
      (t) => t.toLowerCase(),
    ),
  ),
).sort((a, b) => b.length - a.length || (a < b ? -1 : a > b ? 1 : 0));

const GENERIC_ACRONYMS = new Set(LEX.generic_acronyms.map((a) => a.toUpperCase()));
const ORG_SUFFIXES = new Set(LEX.org_suffixes.map((s) => s.toLowerCase()));
const ACRONYM_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(LEX.acronym_map).map(([k, v]) => [k.toUpperCase(), v.toLowerCase()]),
);

const ACRONYM_RE = /\b[A-Z][A-Z0-9]{1,5}\b/g;
const TITLECASE_SEQ_RE = /\b[A-Z][A-Za-z&.'-]+(?:\s+[A-Z][A-Za-z&.'-]+)+\b/g;
const NUMBER_RE = /\d[\d,]*(?:\.\d+)?/g;

export interface Entity {
  text: string;
  kind: "acronym" | "lexicon" | "org";
}

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function norm(text: string): string {
  return (text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

export function numericTokens(text: string): Set<string> {
  const out = new Set<string>();
  for (const m of (text || "").matchAll(NUMBER_RE)) out.add(m[0].replace(/,/g, ""));
  return out;
}

export function taxonomyCovered(phrase: string): boolean {
  const n = norm(phrase);
  return TARGET_TITLES.some((t) => n.includes(t));
}

export function taxonomyPhrase(phrase: string): boolean {
  const n = norm(phrase);
  return TARGET_TITLES.some((t) => n.includes(t) || t.includes(n));
}

function looksLikeOrg(seq: string): boolean {
  return seq.split(/\s+/).some((tok) => ORG_SUFFIXES.has(tok.replace(/^[.,]+|[.,]+$/g, "").toLowerCase()));
}

export function hardEntities(text: string): Entity[] {
  const out: Entity[] = [];
  const seen = new Set<string>();
  const add = (t: string, kind: Entity["kind"]) => {
    const key = kind + "|" + (kind === "acronym" ? t.toUpperCase() : norm(t));
    if (!seen.has(key)) {
      seen.add(key);
      out.push({ text: t, kind });
    }
  };

  for (const m of (text || "").matchAll(ACRONYM_RE)) {
    if (!GENERIC_ACRONYMS.has(m[0].toUpperCase())) add(m[0], "acronym");
  }
  for (const term of CLAIM_TERMS) {
    const m = new RegExp("\\b" + esc(term) + "\\b", "i").exec(text || "");
    if (m) add(m[0], "lexicon"); // keep the resume's surface form (e.g. 'Epic')
  }
  for (const m of (text || "").matchAll(TITLECASE_SEQ_RE)) {
    if (looksLikeOrg(m[0])) add(m[0], "org");
  }
  return out;
}

export function entityGrounded(entity: Entity, resume: string): boolean {
  const { text, kind } = entity;
  if (taxonomyCovered(text)) return true;
  if (kind === "acronym") {
    if (new RegExp("\\b" + esc(text) + "\\b").test(resume)) return true;
    const expansion = ACRONYM_MAP[text.toUpperCase()];
    return Boolean(expansion && norm(resume).includes(expansion));
  }
  return norm(resume).includes(norm(text));
}
