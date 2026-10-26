import { expect, it, vi } from "vitest";
import { guideFrame } from "../src/settingrows";

/** A guide frame with only what landing on a page touches: the page's first
 * heading, or none, as on an error page. */
function landing(heading: string | null) {
  const heard: (() => void)[] = [];
  const frame = {
    contentDocument: {
      querySelector: () => (heading === null ? null : { textContent: heading }),
    },
    contentWindow: { addEventListener() {} },
    addEventListener: (_: string, on: () => void) => heard.push(on),
  };
  vi.stubGlobal("document", { createElement: () => frame });
  const titles: string[] = [];
  guideFrame("/app/theory", "Auditor's Coding Guide", (t) => titles.push(t));
  heard.forEach((on) => on());
  return titles;
}

// R-0567
it("names the row by the page's heading, and keeps the guide's name on a page with none", () => {
  expect(landing("Anxiety (A)")).toEqual(["Anxiety (A)"]);
  expect(landing(null)).toEqual(["Auditor's Coding Guide"]);
});
