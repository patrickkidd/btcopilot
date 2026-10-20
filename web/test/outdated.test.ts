import { expect, it } from "vitest";
import { Failed } from "../src/api";
import { ask, BUSY, lineClass, phase, Phase, rewritten, stamp, UNWRITTEN } from "../src/outdated";
import { RewriteState, type OutOfDate, type Rewrite } from "../src/types";

const out: OutOfDate = { change_id: 41, at: "2026-10-07T09:00:00", sentence: "Delphine's 1995 diagnosis was added after the coach wrote this report." };

// R-0826
it("asks with the sheet when the report is out of date and nothing was answered on this device", () => {
  expect(phase(out, [null], false)).toBe(Phase.Asking);
});

// R-0827
it("asks again when something changed after the change the last report was shown for", () => {
  expect(phase(out, [stamp({ ...out, change_id: 40 })], false)).toBe(Phase.Asking);
});

// R-0827
it("shows only the grey line when the last report was shown for this change", () => {
  expect(phase(out, [stamp(out)], false)).toBe(Phase.Behind);
});

// R-0827
it("asks again when the report is out of date for a reason other than the one the last report was shown for, even under a lower change number", () => {
  const marked = { ...out, change_id: 30, at: "2026-10-15T12:00:00" };
  expect(phase(marked, [stamp(out)], false)).toBe(Phase.Asking);
  expect(phase({ ...out, at: "2026-10-16T08:00:00" }, [stamp(out)], false)).toBe(Phase.Asking);
});

// R-0825, R-0827
it("says nothing on a report that is up to date, and dims the coach's cards while it rewrites them", () => {
  expect(phase(null, [], false)).toBe(Phase.Current);
  expect(phase(out, [], true)).toBe(Phase.Rewriting);
  expect(phase(null, [stamp(out)], true)).toBe(Phase.Rewriting);
});

// R-0826, R-0827
it("asks with the change's own sentence, Refresh the report and Show the last report, and no close button", () => {
  const sheet = ask(out.sentence, (s) => s);
  expect(sheet).toContain("This report is out of date");
  expect(sheet).toContain(out.sentence);
  expect(sheet).toContain("The coach can rewrite its eight cards now. Or you can read the report as it was last written.");
  expect(sheet).toContain(">Refresh the report<");
  expect(sheet).toContain(">Show the last report<");
  expect(sheet).not.toContain("cardx");
});

function rewriter(start: () => Promise<Rewrite | null>, polled: Rewrite[]) {
  const said: string[] = [];
  return {
    said,
    start,
    poll: async () => polled.shift()!,
    pause: async () => {},
    say: (text: string) => said.push(text),
  };
}

// R-0825
it("says a rewrite that failed or that the server no longer knows, and says nothing of one that finished", async () => {
  const running = { id: "r1", state: RewriteState.Running };
  const done = rewriter(async () => running, [running, { id: "r1", state: RewriteState.Done }]);
  expect(await rewritten(done)).toBe(true);
  expect(done.said).toEqual([]);
  const failed = rewriter(async () => running, [{ id: "r1", state: RewriteState.Failed }]);
  await expect(rewritten(failed)).rejects.toThrow("rewrite r1");
  expect(failed.said).toEqual([UNWRITTEN]);
  const lost = rewriter(async () => running, []);
  lost.poll = async () => {
    throw new Failed(404, "GET /case-report-rewrites/r1", "gone");
  };
  await expect(rewritten(lost)).rejects.toThrow("rewrite r1");
  expect(lost.said).toEqual([UNWRITTEN]);
  const busy = rewriter(async () => {
    throw new Failed(409, "POST /case-report-rewrites", "running");
  }, []);
  expect(await rewritten(busy)).toBe(false);
  expect(busy.said).toEqual([BUSY]);
});

// R-0825
it("shows the three dots a working button shows on the grey line while the coach rewrites, and only then", () => {
  expect(lineClass(Phase.Rewriting).split(" ")).toContain("dots3");
  expect(lineClass(Phase.Asking).split(" ")).not.toContain("dots3");
  expect(lineClass(Phase.Behind).split(" ")).not.toContain("dots3");
});
