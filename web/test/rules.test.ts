import { readFileSync, readdirSync } from "node:fs";
import { beforeEach, expect, it } from "vitest";
import { flagLine } from "../src/rules";
import { RuleSource, type Rule } from "../src/types";

const rule = (flagged: boolean): Rule => ({
  id: 7,
  text: "Date a shift by when it began",
  source: {},
  drafted_by: RuleSource.Human,
  flags: [],
  flagged,
  ratified_at: null,
  retired_at: null,
});

const signIn = (admin: boolean) => {
  (globalThis as { window?: unknown }).window = globalThis;
  window.BOOTSTRAP = {
    user: { username: "someone", admin, pro: false, coder: true },
    diagram: null,
    session: null,
    statements: [],
    version: "3.0.0",
  };
};

beforeEach(() => signIn(false));

// R-0346
it("a coder reads that a guideline is flagged, and taps nothing", () => {
  const said = flagLine(rule(true), "rl-flag");
  expect(said).toContain("flagged for the next meeting");
  expect(said).not.toContain("<button");
});

// R-0346
it("a coder sees nothing at all when no flag stands", () => {
  expect(flagLine(rule(false), "rl-flag")).toBe("");
});

// R-0346
it("Patrick gets the tap, on and off", () => {
  signIn(true);
  expect(flagLine(rule(false), "rl-flag")).toContain("flag for next meeting");
  expect(flagLine(rule(false), "rl-flag")).toContain("<button");
  expect(flagLine(rule(true), "rl-flag")).toContain("flagged for the next meeting");
  expect(flagLine(rule(true), "rl-flag")).toContain("<button");
});

// R-0310
it("calls them coding guidelines on screen, never the codebook", () => {
  const page = readFileSync("../btcopilot/personal/static/web/index.html", "utf8");
  expect(page).toContain('id="coding-info" type="button" aria-label="Coding guidelines"');
  const sources = readdirSync("src").map((f) => readFileSync(`src/${f}`, "utf8"));
  expect([page, ...sources].filter((text) => /codebook/i.test(text))).toEqual([]);
});
