import { expect, it } from "vitest";
import { ask, phase, Phase } from "../src/outdated";
import type { OutOfDate } from "../src/types";

const out: OutOfDate = { change_id: 41, at: "2026-10-07T09:00:00", sentence: "Delphine's 1995 diagnosis was added after the coach wrote this report." };

// R-0713
it("asks with the sheet when the report is out of date and nothing was answered on this device", () => {
  expect(phase(out, null, false)).toBe(Phase.Asking);
});

// R-0713
it("asks again when something changed after the change the last report was shown for", () => {
  expect(phase(out, 40, false)).toBe(Phase.Asking);
});

// R-0713
it("shows only the grey line when the last report was shown for this change", () => {
  expect(phase(out, 41, false)).toBe(Phase.Behind);
});

// R-0713
it("says nothing on a report that is up to date, and dims the coach's cards while it rewrites them", () => {
  expect(phase(null, null, false)).toBe(Phase.Current);
  expect(phase(out, null, true)).toBe(Phase.Rewriting);
  expect(phase(null, 41, true)).toBe(Phase.Rewriting);
});

// R-0713
it("asks with the change's own sentence, Refresh the report and Show the last report, and no close button", () => {
  const sheet = ask(out.sentence, (s) => s);
  expect(sheet).toContain("This report is out of date");
  expect(sheet).toContain(out.sentence);
  expect(sheet).toContain("The coach can rewrite its five cards now. Or you can read the report as it was last written.");
  expect(sheet).toContain(">Refresh the report<");
  expect(sheet).toContain(">Show the last report<");
  expect(sheet).not.toContain("cardx");
});
