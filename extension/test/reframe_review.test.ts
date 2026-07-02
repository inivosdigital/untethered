import { test, expect } from "vitest";
import { reviewProposals, renderReview, type Review } from "../src/reframe/review";
import { SAMPLE_EDITS, SAMPLE_RESUME } from "../src/reframe/sample";
import type { Edit } from "../src/reframe/types";

test("full_reframe accepts the grounded edits and abstains the fabrications", () => {
  const r = reviewProposals(SAMPLE_EDITS, SAMPLE_RESUME, "full_reframe");
  expect(r.accepted.length).toBe(3);
  expect(r.abstained.length).toBe(2); // invented 34% metric + invented Epic Resolute
  const reasons = r.abstained.flatMap((a) => a.reasons.map((s) => s.split(":")[0]));
  expect(reasons).toContain("fabricated_metric");
  expect(reasons).toContain("fabricated_entity");
  expect(r.newSearchTerms).toContain("denials");
  expect(r.newSearchTerms).toContain("revenue cycle");
});

test("title_only keeps only the headline relabel; the rest are held by mode", () => {
  const r = reviewProposals(SAMPLE_EDITS, SAMPLE_RESUME, "title_only");
  expect(r.accepted.length).toBe(1);
  expect(r.accepted[0].field).toBe("headline");
  expect(r.modeFiltered.length).toBe(2); // grounded summary + bullet, out of scope
});

test("control is a no-op review", () => {
  const r = reviewProposals(SAMPLE_EDITS, SAMPLE_RESUME, "control");
  expect(r.accepted).toEqual([]);
  expect(r.abstained).toEqual([]);
});

test("renderReview escapes edit text (no XSS)", () => {
  const evil: Edit = {
    field: "summary", change_type: "reemphasis",
    source_span: "x", before: "x", after: "<script>alert(1)</script>",
    surfaced_keywords: [], rationale: "<b>hi</b>",
  };
  const review: Review = {
    mode: "full_reframe", accepted: [evil], abstained: [], modeFiltered: [], newSearchTerms: [],
  };
  const html = renderReview(review);
  expect(html).toContain("&lt;script&gt;");
  expect(html).not.toContain("<script>");
  expect(html).toContain("&lt;b&gt;hi&lt;/b&gt;");
});
