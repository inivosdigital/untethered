// Client-side reframe review: run the grounding guard on LLM proposals, gate by
// mode, and render the result. Mirrors reframe/engine.py (guard + mode-gate) and
// reframe/diff.py (visible diff). No apply step - the panel shows the candidate's
// changes and lets them decide; the resume never leaves the device to be judged.
import { checkEdit } from "./guard";
import { norm, TARGET_TITLES } from "./taxonomy";
import type { Edit, FieldName } from "./types";

export type Mode = "control" | "title_only" | "full_reframe";

const MODE_KEEP: Record<Mode, (e: Edit) => boolean> = {
  control: () => false,
  title_only: (e) => e.field === "headline" && e.change_type === "relabel",
  full_reframe: () => true,
};

export interface Review {
  mode: Mode;
  accepted: Edit[];
  abstained: { edit: Edit; reasons: string[] }[];
  modeFiltered: Edit[];
  newSearchTerms: string[];
}

export function reviewProposals(edits: Edit[], resume: string, mode: Mode): Review {
  const keep = MODE_KEEP[mode];
  const accepted: Edit[] = [];
  const abstained: { edit: Edit; reasons: string[] }[] = [];
  const modeFiltered: Edit[] = [];

  const list = mode === "control" ? [] : edits;
  for (const e of list) {
    const reasons = checkEdit(e, resume); // guard runs on the WHOLE resume
    if (reasons.length) abstained.push({ edit: e, reasons });
    else if (keep(e)) accepted.push(e);
    else modeFiltered.push(e);
  }

  // recruiter-search terms that the accepted edits newly surface
  const appliedNorm = norm(resume + " " + accepted.map((e) => e.after).join(" "));
  const resumeNorm = norm(resume);
  const newSearchTerms = TARGET_TITLES.filter(
    (t) => appliedNorm.includes(t) && !resumeNorm.includes(t),
  );

  return { mode, accepted, abstained, modeFiltered, newSearchTerms };
}

// --------------------------------------------------------------------------- //
// Rendering (returns an HTML string; the panel assigns it to innerHTML)
// --------------------------------------------------------------------------- //

const ESCAPE: Record<string, string> = {
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
};
export const esc = (s: unknown) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESCAPE[c]);

const FIELD_LABEL: Record<FieldName, string> = {
  headline: "headline", summary: "summary", bullet: "bullet", skills: "skills",
};

const REASON_TEXT: Record<string, string> = {
  empty_after: "proposed text was empty",
  no_op: "did not change anything",
  ungrounded_span: "anchor not found verbatim in your resume",
  ungrounded_before: "original text not found verbatim in your resume",
  relabel_no_keyword: "relabel surfaced no recruiter keyword",
  keyword_absent_from_after: "claimed keyword not present in the new text",
};

export function explainReason(reason: string): string {
  const i = reason.indexOf(":");
  if (i >= 0) {
    const kind = reason.slice(0, i);
    const detail = reason.slice(i + 1);
    if (kind === "fabricated_metric") return `invented number not in your resume: ${detail}`;
    if (kind === "fabricated_entity") return `invented credential/employer not in your resume: ${detail}`;
    if (kind === "keyword_not_in_taxonomy") return `keyword outside the recruiter-search vocabulary: ${detail}`;
  }
  return REASON_TEXT[reason] || reason;
}

export function renderReview(r: Review): string {
  if (r.mode === "control") {
    return `<div class="card"><div class="rf-h">Re-Frame · control</div>
      <div class="reasons">Baseline arm: your resume is left unchanged.</div></div>`;
  }

  const changes = r.accepted.length
    ? r.accepted.map((e, i) => `<div class="rf-edit">
        <div class="rf-edit-head">${i + 1}. ${pillTag(FIELD_LABEL[e.field])} ${pillTag(e.change_type)}</div>
        <div class="rf-before">- ${esc(e.before)}</div>
        <div class="rf-after">+ ${esc(e.after)}</div>
        ${e.surfaced_keywords.length ? `<div class="rf-kw">surfaces: ${esc(e.surfaced_keywords.join(", "))}</div>` : ""}
        <div class="rf-why">why: ${esc(e.rationale)}</div>
      </div>`).join("")
    : `<div class="reasons">No changes survived the grounding guard.</div>`;

  const terms = r.newSearchTerms.length
    ? `<div class="rf-terms"><div class="rf-sub">New recruiter-search terms now present:</div>
        ${r.newSearchTerms.map((t) => `<span class="pill ok">${esc(t)}</span>`).join(" ")}</div>`
    : `<div class="rf-terms"><div class="rf-sub">No new recruiter-search terms added.</div></div>`;

  const dropped = r.abstained.length
    ? `<div class="rf-drop"><div class="rf-sub">Dropped as ungrounded (${r.abstained.length}):</div>
        ${r.abstained.map((a) => `<div class="rf-dropped">
          <div class="rf-dropped-text">${esc(a.edit.after)}</div>
          ${a.reasons.map((rn) => `<div class="rf-x">✕ ${esc(explainReason(rn))}</div>`).join("")}
        </div>`).join("")}</div>`
    : "";

  const held = r.modeFiltered.length
    ? `<div class="reasons">${r.modeFiltered.length} grounded change(s) held back - out of scope for “${esc(r.mode)}”.</div>`
    : "";

  return `<div class="card">
    <div class="rf-h">Re-Frame · ${esc(r.mode)}</div>
    <div class="rf-sub">Accepted changes (${r.accepted.length}):</div>
    ${changes}${terms}${dropped}${held}
  </div>`;
}

function pillTag(s: string): string {
  return `<span class="tag">${esc(s)}</span>`;
}
