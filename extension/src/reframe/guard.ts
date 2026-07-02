// Deterministic grounding guard - EXACT TypeScript mirror of
// reframe/guardrails.py check_edit. Runs client-side in the extension so the
// resume never leaves the browser to be validated (score-don't-store). Returns
// the same stable reason strings as the Python guard; cross-language parity is
// enforced by scoring/reframe_guard_parity_fixtures.json.
import type { Edit } from "./types";
import {
  entityGrounded,
  hardEntities,
  norm,
  numericTokens,
  taxonomyPhrase,
} from "./taxonomy";

function grounded(span: string, resume: string): boolean {
  span = (span || "").trim();
  return span.length > 0 && norm(resume).includes(norm(span));
}

/** Return de-duplicated abstain reasons for an edit. Empty array == ACCEPT. */
export function checkEdit(edit: Edit, resume: string): string[] {
  const reasons: string[] = [];

  // 1. structural
  if (!(edit.after || "").trim()) reasons.push("empty_after");
  if (norm(edit.after) === norm(edit.before)) reasons.push("no_op");

  // 2. span grounding
  if (!grounded(edit.source_span, resume)) reasons.push("ungrounded_span");
  if ((edit.before || "").trim() && !grounded(edit.before, resume)) {
    reasons.push("ungrounded_before");
  }

  // 3. numeric grounding
  const resumeNums = numericTokens(resume);
  const newNumbers = [...numericTokens(edit.after)].filter((n) => !resumeNums.has(n));
  if (newNumbers.length) reasons.push("fabricated_metric:" + newNumbers.sort().join(","));

  // 4. entity grounding
  for (const ent of hardEntities(edit.after)) {
    if (!entityGrounded(ent, resume)) reasons.push("fabricated_entity:" + ent.text);
  }

  // 5. relabel discipline
  if (edit.change_type === "relabel") {
    if (!edit.surfaced_keywords.length) reasons.push("relabel_no_keyword");
    for (const kw of edit.surfaced_keywords) {
      if (!taxonomyPhrase(kw)) reasons.push("keyword_not_in_taxonomy:" + kw);
    }
    const present = edit.surfaced_keywords.filter((kw) => norm(edit.after).includes(norm(kw)));
    if (edit.surfaced_keywords.length && !present.length) reasons.push("keyword_absent_from_after");
  }

  // de-dupe, preserve order
  const seen = new Set<string>();
  return reasons.filter((r) => (seen.has(r) ? false : (seen.add(r), true)));
}
