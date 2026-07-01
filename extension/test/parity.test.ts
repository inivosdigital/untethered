import { test, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { scoreJob } from "../src/score";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("scoring engine reproduces the golden verdicts (parity with Python)", () => {
  const data = JSON.parse(readFileSync(join(ROOT, "scoring", "parity_fixtures.json"), "utf8"));
  expect(data.postings.length).toBeGreaterThanOrEqual(10);
  for (const post of data.postings) {
    const p = { title: post.title, description: post.description, workplace: post.workplace,
      location: post.location, payHourly: post.payHourly };
    const s = scoreJob(p);
    const got = { rcm: s.rcm, roleArchetype: s.roleArchetype, remote: s.remote, pay: s.pay,
      offshoreResistant: s.offshoreResistant, credential: s.credential, qualifies: s.qualifies };
    expect(got, `verdict drift on ${post.title}`).toEqual(post.expect);
  }
});

test("extension rules.json is identical to the canonical scoring/rules.json", () => {
  const canonical = JSON.parse(readFileSync(join(ROOT, "scoring", "rules.json"), "utf8"));
  const copy = JSON.parse(readFileSync(join(ROOT, "extension", "src", "scoring", "rules.json"), "utf8"));
  expect(copy).toEqual(canonical);
});
