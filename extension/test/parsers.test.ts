import { test, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parsePayFromText, stripHtml } from "../src/normalizer";
import { scoreJob } from "../src/score";
import { parseWorkdayList, parseWorkdayDetail, workdayContext } from "../src/parsers/workday";
import { parseJsonLdObject } from "../src/parsers/jsonld";

const FX = join(dirname(fileURLToPath(import.meta.url)), "..", "fixtures");
const load = (f: string) => JSON.parse(readFileSync(join(FX, f), "utf8"));

test("normalizer: strip HTML entities + tags", () => {
  expect(stripHtml("&lt;p&gt;Denials &amp; appeals&lt;/p&gt;")).toBe("Denials & appeals");
});

test("normalizer: hourly range reads the LOWER bound", () => {
  expect(parsePayFromText("Pay range $32 - $40 per hour").hourly).toBe(32);
});

test("normalizer: straddling range does not report its top", () => {
  expect(parsePayFromText("Compensation $22 - $34 per hour").hourly).toBe(22);
  expect(Math.abs((parsePayFromText("Salary $45,000 - $70,000 per year").hourly ?? 0) - 45000 / 2080)).toBeLessThan(0.1);
});

test("normalizer: annual salary; standalone bonus ignored", () => {
  expect(Math.abs((parsePayFromText("The annual salary is $75,000 for this role.").hourly ?? 0) - 75000 / 2080)).toBeLessThan(0.1);
  expect(parsePayFromText("Up to $10,000 signing bonus for new hires").hourly).toBeNull();
});

test("workday: context parsed from careers URL", () => {
  expect(workdayContext("https://devoted.wd1.myworkdayjobs.com/en-US/Devoted/job/Remote-USA/x_R1"))
    .toEqual({ tenant: "devoted", site: "Devoted", origin: "https://devoted.wd1.myworkdayjobs.com", externalPath: "/Remote-USA/x_R1" });
});

test("workday: parse LIST fixture -> light postings", () => {
  const ctx = { tenant: "devoted", site: "Devoted", origin: "https://devoted.wd1.myworkdayjobs.com", employer: "Devoted Health" };
  const list = parseWorkdayList(load("workday_devoted_jobs.json"), ctx);
  expect(list.length).toBe(20);
  expect(list[0].source).toBe("workday");
  expect(list[0].url).toContain("/en-US/Devoted");
});

test("workday: parse DETAIL fixture -> pay text-extracted", () => {
  const p = parseWorkdayDetail(load("workday_devoted_job_detail.json"),
    { employer: "Devoted Health", origin: "https://devoted.wd1.myworkdayjobs.com", site: "Devoted" });
  expect(p.title).toBe("Payment Integrity Program Development Manager");
  expect(p.location).toBe("Remote USA");
  expect(p.description.length).toBeGreaterThan(500);
  expect(p.payHourly ?? 0).toBeGreaterThanOrEqual(30);
});

test("scoring: real Workday detail — RCM+remote but MANAGER => not archetype", () => {
  const p = parseWorkdayDetail(load("workday_devoted_job_detail.json"), { employer: "Devoted Health" });
  const s = scoreJob(p);
  expect(s.rcm).toBe(true);
  expect(s.remote).toBe("remote");
  expect(s.roleArchetype).toBe(false);
  expect(s.qualifies).toBe(false);
});

test("jsonld: qualifying accessible IC role (min lower bound)", () => {
  const p = parseJsonLdObject(load("jsonld_sample.json"), { url: "https://boards.example.com/jobs/123" })!;
  expect(p.employer).toBe("Acme Health");
  expect(p.payHourly).toBe(34);
  expect(scoreJob(p).qualifies).toBe(true);
});

test("jsonld: non-USD salary is not normalized as USD", () => {
  const cad = { "@type": "JobPosting", title: "Billing Specialist",
    hiringOrganization: { name: "Maple Health" }, description: "Charge entry and posting.",
    baseSalary: { "@type": "MonetaryAmount", currency: "CAD", value: { minValue: 40, maxValue: 45, unitText: "HOUR" } },
    url: "https://x/1" };
  expect(parseJsonLdObject(cad, {})!.payHourly).toBeNull();
});
