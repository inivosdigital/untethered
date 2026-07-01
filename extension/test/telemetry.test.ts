import { test, expect } from "vitest";
import { applyExtraction, successRate } from "../src/telemetry";

test("telemetry reducer folds extraction outcomes + computes success rate", () => {
  let t = applyExtraction({}, "workday", true);
  t = applyExtraction(t, "workday", true);
  t = applyExtraction(t, "workday", false, "cxs 500");
  expect(t.workday.attempts).toBe(3);
  expect(t.workday.success).toBe(2);
  expect(t.workday.failures).toBe(1);
  expect(t.workday.lastFailure).toBe("cxs 500");
  expect(successRate(t.workday)).toBeCloseTo(2 / 3);
  // independent adapters tracked separately
  const t2 = applyExtraction(t, "jsonld", true);
  expect(t2.jsonld.attempts).toBe(1);
  expect(t2.workday.attempts).toBe(3);
});
