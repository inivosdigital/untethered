// Baked sample for the offline demo path (no backend needed). Mirrors
// reframe/examples/laritza_*. Includes deliberately ungrounded proposals so the
// panel visibly demonstrates the guard rejecting an invented metric, an invented
// system, and invented experience.
import type { Edit } from "./types";

export const SAMPLE_RESUME = `Laritza M.
Medical Billing Representative

Summary
Detail-oriented billing professional with 6 years in a hospital business office. Comfortable working insurance claims and following up with payers.

Experience
Regional Hospital Business Office - Billing Representative
- Worked accounts receivable follow-up on unpaid hospital claims.
- Handled denied claims and filed appeals with commercial and Medicare payers.
- Called insurance companies to resolve claim rejections and underpayments.
- Posted patient payments and reconciled daily batches.

Skills
Insurance follow-up, claim resolution, customer service, Microsoft Excel.`;

export const SAMPLE_EDITS: Edit[] = [
  {
    field: "headline", change_type: "relabel",
    source_span: "Medical Billing Representative", before: "Medical Billing Representative",
    after: "Accounts Receivable / Denials & Appeals Specialist",
    surfaced_keywords: ["accounts receivable", "denials", "appeals"],
    rationale: "Resume shows AR follow-up plus denied claims and appeals work.",
  },
  {
    field: "summary", change_type: "reemphasis",
    source_span: "Detail-oriented billing professional with 6 years in a hospital business office. Comfortable working insurance claims and following up with payers.",
    before: "Detail-oriented billing professional with 6 years in a hospital business office. Comfortable working insurance claims and following up with payers.",
    after: "Revenue cycle billing professional with 6 years in a hospital business office, focused on accounts receivable follow-up, denials, and appeals.",
    surfaced_keywords: ["revenue cycle", "accounts receivable", "denials", "appeals"],
    rationale: "Surfaces the AR, denials, and appeals work; keeps the 6-year tenure.",
  },
  {
    field: "bullet", change_type: "reemphasis",
    source_span: "Called insurance companies to resolve claim rejections and underpayments.",
    before: "Called insurance companies to resolve claim rejections and underpayments.",
    after: "Resolved claim denials and underpayments through payer appeals and accounts receivable follow-up.",
    surfaced_keywords: ["denials", "appeals", "accounts receivable"],
    rationale: "Reframes generic phone follow-up into the terms recruiters search.",
  },
  {
    field: "bullet", change_type: "reemphasis",
    source_span: "Worked accounts receivable follow-up on unpaid hospital claims.",
    before: "Worked accounts receivable follow-up on unpaid hospital claims.",
    after: "Reduced accounts receivable aging by 34% across unpaid hospital claims.",
    surfaced_keywords: ["accounts receivable"],
    rationale: "INVENTED metric - must be rejected by the guard.",
  },
  {
    field: "bullet", change_type: "reemphasis",
    source_span: "Posted patient payments and reconciled daily batches.",
    before: "Posted patient payments and reconciled daily batches.",
    after: "Posted patient payments in Epic Resolute and reconciled daily batches.",
    surfaced_keywords: [],
    rationale: "INVENTED system - must be rejected by the guard.",
  },
];
