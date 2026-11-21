import { expect, it } from "vitest";
import { clock, ENDED, Ended, endingFor, kindFor, missedLine, nameFor } from "../src/recorder";

// R-0955
it("records MP4 where the browser can, else WebM, named by when it started and by its kind", () => {
  expect(kindFor((kind) => kind === "audio/mp4" || kind === "audio/webm")).toBe("audio/mp4");
  expect(kindFor((kind) => kind === "audio/webm")).toBe("audio/webm");
  expect(kindFor(() => false)).toBe("");
  expect(endingFor("audio/mp4")).toBe("m4a");
  expect(endingFor("audio/mp4;codecs=opus")).toBe("m4a");
  expect(endingFor("audio/webm;codecs=opus")).toBe("webm");
  expect(nameFor(new Date(2026, 10, 2, 15, 4), "audio/mp4")).toBe("Recording 2026-11-02 15.04.m4a");
});

// R-0955
it("shows the running time, the time missed while hidden, and why a recording stopped early, as values", () => {
  expect(clock(0)).toBe("0:00");
  expect(clock(35.7)).toBe("0:35");
  expect(clock(12 * 60 + 40)).toBe("12:40");
  expect(clock(3723)).toBe("1:02:03");
  expect(missedLine(22.4)).toBe("Missed 0:22 while this screen was hidden");
  expect(ENDED[Ended.Lost]).toBe("Stopped when the microphone was lost");
});
