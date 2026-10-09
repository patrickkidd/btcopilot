import { expect, it } from "vitest";
import { said } from "../src/api";
import { fileChip, Picked, readSheet } from "../src/attachment";

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
  expect(readSheet("<b>.md", "1 < 2")).toContain("1 &lt; 2");
  expect(readSheet("<b>.md", "1 < 2")).toContain("&lt;b&gt;.md");
});
