import { test, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { checkEdit } from "../src/reframe/guard";
import type { Edit } from "../src/reframe/types";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("client-side guard reproduces the Python guard verdicts (cross-language parity)", () => {
  const data = JSON.parse(
    readFileSync(join(ROOT, "scoring", "reframe_guard_parity_fixtures.json"), "utf8"),
  );
  expect(data.cases.length).toBeGreaterThanOrEqual(12);
  for (const c of data.cases) {
    const got = checkEdit(c.edit as Edit, data.resume);
    expect(got, `guard drift on ${c.label}`).toEqual(c.expect_reasons);
  }
});

test("extension reframe/lexicon.json is identical to the canonical reframe/lexicon.json", () => {
  const canonical = JSON.parse(readFileSync(join(ROOT, "reframe", "lexicon.json"), "utf8"));
  const copy = JSON.parse(
    readFileSync(join(ROOT, "extension", "src", "reframe", "lexicon.json"), "utf8"),
  );
  expect(copy).toEqual(canonical);
});
