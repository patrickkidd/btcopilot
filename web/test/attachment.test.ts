import { expect, it } from "vitest";
import { said } from "../src/api";
import { clipChip, clipOf, fileChip, isAudio, KINDS, nameOf, Picked, readSheet, Stage, values } from "../src/attachment";

const pdf = () => new File(["%PDF"], "Mom's letter.pdf", { type: "application/pdf" });

// R-0828
it("keeps one file for the next message, a second pick taking the first one's place, and sends it once", () => {
  const box = new Picked();
  expect(box.take()).toBeNull();
  box.pick(new File(["a"], "notes.md"));
  box.pick(pdf());
  expect(box.file!.name).toBe("Mom's letter.pdf");
  expect(box.take()!.name).toBe("Mom's letter.pdf");
  expect(box.file).toBeNull();
  expect(box.take()).toBeNull();
});

// R-0828
it("sends the words, the time zone and the file as one form", () => {
  const form = said("Here is her letter", "America/Anchorage", pdf());
  expect(form.get("statement")).toBe("Here is her letter");
  expect(form.get("time_zone")).toBe("America/Anchorage");
  expect((form.get("file") as File).name).toBe("Mom's letter.pdf");
});

// R-0829, R-0830
it("shows the file's name still while it is read, and once read a chip that opens what the coach read", () => {
  const reading = fileChip("Mom's letter.pdf");
  expect(reading).toContain('class="chip file reading"');
  expect(reading).toContain("disabled");
  expect(reading).toContain("Mom&#39;s letter.pdf");
  const read = fileChip("Mom's letter.pdf", "Dear Ann,");
  expect(read).not.toContain("reading");
  expect(read).not.toContain("disabled");
  const untaken = fileChip("Mom's letter.pdf", null, true);
  expect(untaken).toContain('class="chip file untaken"');
  expect(untaken).toContain("disabled");
  expect(readSheet("<b>.md", "1 < 2")).toContain("1 &lt; 2");
  expect(readSheet("<b>.md", "1 < 2")).toContain("&lt;b&gt;.md");
});

const memo = () => new File(["audio"], "Talk with Uncle Gerald.m4a", { type: "audio/mp4" });

// R-0953, R-0954
it("takes a recording through the same picker as any other document", () => {
  for (const kind of [".pdf", ".txt", ".m4a", ".mp3", "audio/*"]) expect(KINDS.split(",")).toContain(kind);
  expect(isAudio(memo())).toBe(true);
  expect(isAudio(new File(["a"], "Voice 014.M4A"))).toBe(true);
  expect(isAudio(pdf())).toBe(false);
});

// R-0953
it("says where a recording in the box has got as values, not a sentence", () => {
  const clip = clipOf(memo());
  clip.sent = 0.4;
  expect(values(clip, 0)).toEqual(["Uploading 40%"]);
  Object.assign(clip, { stage: Stage.Transcribing, since: 1000 });
  expect(values(clip, 36_000)).toEqual(["Transcribing 0:35"]);
  Object.assign(clip, { stage: Stage.Named, seconds: 46 * 60 + 10, voices: [{}, {}] });
  expect(values(clip, 0)).toEqual(["Length 46 min", "Speakers 2"]);
  expect(clipChip(clip, 0)).toContain("Length 46 min · Speakers 2");
  expect(clipChip(clip, 0)).toContain("Talk with Uncle Gerald.m4a");
  clip.stage = Stage.Failed;
  const failed = clipChip(clip, 0);
  expect(failed).toContain("Could not transcribe");
  expect(failed).toContain('data-act="again"');
  expect(failed).toContain('data-act="remove"');
  clip.stage = Stage.Silent;
  expect(clipChip(clip, 0)).toContain("No speech found");
  expect(clipChip(clip, 0)).not.toContain('data-act="again"');
});

// R-0954
it("sends a recording as its transcript and who each speaker is, in the form a file goes in", () => {
  const form = said("This is the talk with my uncle", "America/Phoenix", {
    transcription: "t-7",
    voices: { A: { person_id: 5 }, B: { name: "Aunt Rosalie" } },
    title: "Talk with Uncle Gerald",
    date: "2026-11-02",
  });
  expect(form.get("file")).toBeNull();
  expect(form.get("transcription")).toBe("t-7");
  expect(JSON.parse(form.get("voices") as string)).toEqual({ A: { person_id: 5 }, B: { name: "Aunt Rosalie" } });
  expect(form.get("title")).toBe("Talk with Uncle Gerald");
  expect(form.get("date")).toBe("2026-11-02");
  expect(nameOf(memo())).toBe("Talk with Uncle Gerald.m4a");
});
