import { test, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { postedEstimate, oewsPrior, crowdAggregate } from "../src/pay";

const FIX = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "scoring", "pay_parity_fixtures.json");

function run(c: any) {
  if (c.kind === "posted-structured") return postedEstimate({ structured: c.input });
  if (c.kind === "posted-text") return postedEstimate({ text: c.input });
  if (c.kind === "oews") return oewsPrior(c.input);
  if (c.kind === "crowd") return crowdAggregate(c.input);
  throw new Error(c.kind);
}

test("pay engine reproduces the golden PayEstimates (parity with Python)", () => {
  const data = JSON.parse(readFileSync(FIX, "utf8"));
  expect(data.cases.length).toBeGreaterThanOrEqual(10);
  for (const c of data.cases) {
    const got = run(c) ?? null;
    expect(got, `pay verdict drift on ${c.id}`).toEqual(c.expect);
  }
});
