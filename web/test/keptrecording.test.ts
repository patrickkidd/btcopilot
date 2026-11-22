import { expect, it, vi } from "vitest";
import { type About, KeptRecording, type Shelf } from "../src/keptrecording";
import { rebuilt } from "../src/recorder";

/** The device's storage, in memory, ordered by key as IndexedDB orders it:
 * numbers before words. */
class Memory implements Shelf {
  kept = new Map<IDBValidKey, unknown>();
  refuse = false;

  async put(key: IDBValidKey, value: unknown): Promise<void> {
    if (this.refuse) throw new DOMException("The quota has been exceeded.", "QuotaExceededError");
    this.kept.set(key, value);
  }

  async entries(): Promise<[IDBValidKey, unknown][]> {
    const rank = (key: IDBValidKey) => (typeof key === "number" ? 0 : 1);
    return [...this.kept].sort(([a], [b]) => rank(a) - rank(b) || (a < b ? -1 : a > b ? 1 : 0));
  }

  async clear(): Promise<void> {
    this.kept.clear();
  }
}

const about: About = {
  kind: "audio/mp4",
  started: new Date(2026, 10, 21, 14, 5).getTime(),
  seconds: 0,
  missed: 0,
  diagram: 7,
  name: "Hartley family",
};

const piece = (text: string) => new Blob([text], { type: "audio/mp4" });

function recorded(memory = new Memory()) {
  const kept = new KeptRecording(async () => memory);
  kept.begin(about);
  ["one ", "two ", "three ", "four ", "five ", "six ", "seven ", "eight ", "nine ", "ten ", "eleven ", "twelve"].forEach(
    (text, i) => kept.add(piece(text), i + 1, 0, "audio/mp4"),
  );
  return { kept, memory };
}

const text = (pieces: ArrayBuffer[]) => pieces.map((one) => new TextDecoder().decode(one)).join("");

// R-0955
it("keeps every piece of sound in order, with the running time of the last", async () => {
  const { kept } = recorded();
  const found = await kept.find();
  expect(text(found!.pieces)).toBe("one two three four five six seven eight nine ten eleven twelve");
  expect(found!.about).toEqual({ ...about, seconds: 12 });
});

// R-0955
it("finds the recording again after the page reloads, from the device's storage alone", async () => {
  const { kept, memory } = recorded();
  await kept.written();
  const found = await new KeptRecording(async () => memory).find();
  expect(found!.about.name).toBe("Hartley family");
  expect(found!.about.diagram).toBe(7);
  expect(found!.pieces).toHaveLength(12);
});

// R-0955
it("rebuilds on Keep the same bytes, kind and name Stop would have given", async () => {
  const { kept, memory } = recorded();
  await kept.written();
  const file = rebuilt((await new KeptRecording(async () => memory).find())!);
  expect(await file.text()).toBe("one two three four five six seven eight nine ten eleven twelve");
  expect(file.type).toBe("audio/mp4");
  expect(file.name).toBe("Recording 2026-11-21 14.05.m4a");
});

// R-0955
it("is removed once the server has taken the upload, or the person discards it, and not before", async () => {
  const { kept, memory } = recorded();
  await kept.written();
  expect(memory.kept.size).toBe(13);
  kept.forget();
  expect(await kept.find()).toBeNull();
  expect(memory.kept.size).toBe(0);
});

// R-0955
it("keeps one recording at a time: a new one takes the old one's place", async () => {
  const { kept } = recorded();
  kept.begin({ ...about, started: about.started + 60_000 });
  expect(await kept.find()).toBeNull();
  kept.add(piece("again"), 1, 0, "audio/mp4");
  const found = await kept.find();
  expect(text(found!.pieces)).toBe("again");
  expect(found!.about.started).toBe(about.started + 60_000);
});

// R-0955
it("goes on recording in memory when the device will not store it, and says so in the console", async () => {
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  const memory = new Memory();
  memory.refuse = true;
  const { kept } = recorded(memory);
  await kept.written();
  expect(warn).toHaveBeenCalledTimes(1);
  expect(warn.mock.calls[0][0]).toContain("kept in memory only");
  expect(await kept.find()).toBeNull();
  const none = new KeptRecording(async () => {
    throw new DOMException("No storage on this device", "NotSupportedError");
  });
  none.begin(about);
  none.add(piece("one"), 1, 0, "audio/mp4");
  await none.written();
  expect(warn).toHaveBeenCalledTimes(2);
  warn.mockRestore();
});
