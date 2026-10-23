import { afterEach, expect, it, vi } from "vitest";

vi.stubGlobal("window", { BOOTSTRAP: { user: { username: "ann", pro: false } } });

const { ADD_CODES, Answer, bring, fromDrop, fromPicked, Importer, PICKLE, refusal, TOO_BIG } = await import(
  "../src/importer"
);

afterEach(() => vi.unstubAllGlobals());

/** A folder as a drop hands it over: read in batches until one comes back
 * empty. */
const folder = (name: string, files: File[]) => {
  const batches = [files.slice(0, 1), files.slice(1), []];
  return {
    name,
    isDirectory: true,
    createReader: () => ({ readEntries: (done: (batch: unknown[]) => void) => done(batches.shift()!.map(entry)) }),
  };
};
const entry = (file: File) => ({ isFile: true, file: (done: (file: File) => void) => done(file) });
const dropped = (item: unknown, files: File[] = []) =>
  ({ items: [{ webkitGetAsEntry: () => item }], files }) as unknown as DataTransfer;

// R-0899
it("finds the diagram.pickle in a dropped .fd folder and sends it under the folder's name", async () => {
  const pickle = new File(["\x80\x03}q"], PICKLE);
  const sent = await fromDrop(dropped(folder("Lund family.fd", [new File(["x"], "image.png"), pickle])));
  expect(sent!.name).toBe("Lund family.fd");
  expect(await sent!.text()).toBe(await pickle.text());
  expect(await fromDrop(dropped(folder("Photos", [new File(["x"], "image.png")])))).toBeNull();
});

/** A file as a browser's picker gives it: with its path inside the folder
 * picked, or "" when one file was picked. */
const within = (path: string, name = path.split("/").pop()!): File => {
  const file = new File(["x"], name);
  Object.defineProperty(file, "webkitRelativePath", { value: path });
  return file;
};

// R-0899
it("takes a picked folder's own diagram.pickle, not one deeper in it, and a picked .zip as it is", () => {
  const sent = fromPicked([within("Lund family.fd/Backups/diagram.pickle"), within(`Lund family.fd/${PICKLE}`)])!;
  expect(sent.name).toBe("Lund family.fd");
  expect(fromPicked([within("Lund family.fd/Backups/diagram.pickle")])).toBeNull();
  expect(fromPicked([within("", "Lund family.fd.zip")])!.name).toBe("Lund family.fd.zip");
});

const answering = (status: number, body: string) => {
  const sent: FormData[] = [];
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    sent.push(init.body as FormData);
    return new Response(body, { status });
  });
  return sent;
};

const lund = { id: 9, name: "Lund family", imported: { people: 41, events: 212, left_out: 3 } };

/** The importer with its sheet and what it hands on recorded. */
const importer = () => {
  const done = { opened: [] as unknown[], said: [] as string[], shown: [] as string[], lowered: 0 };
  const one = Object.assign(Object.create(Importer.prototype), {
    sending: false,
    opened: async (made: unknown) => void done.opened.push(made),
    say: (words: string) => void done.said.push(words),
    sheet: { show: (html: string) => void done.shown.push(html), lower: () => void done.lowered++ },
  });
  return { one, done };
};

// R-0899, R-0902, R-0905
it("opens the new diagram and then says how much of the file came in", async () => {
  const sent = answering(201, JSON.stringify(lund));
  const { one, done } = importer();
  await one.send(new File(["\x80\x03}q"], "Lund family.fd.zip"));
  expect([sent[0].get("name"), sent[0].has("coding")]).toEqual(["Lund family", false]);
  expect(done.opened).toEqual([lund]);
  expect(done.shown[0]).toContain("Your file is in: 41 people and 212 events.");
  expect(done.shown[0]).toContain("3 could not be brought in; the coach will ask about them.");
  expect(done.shown[0]).toContain("Should the coach go through the events and add codes where the file has none?");
});

// R-0899, R-0902, R-0905
it("sends the coach the prepared words on Yes, and nothing on Not now", () => {
  const yes = importer();
  yes.one.answer(Answer.Yes);
  expect(yes.done.said).toEqual([ADD_CODES]);
  const no = importer();
  no.one.answer(Answer.NotNow);
  expect([no.done.said, no.done.lowered]).toEqual([[], 1]);
});

// R-0899
it("shows the server's own sentence for a file it refuses, and refuses one over 20 MB before sending", async () => {
  answering(400, "That file was saved by an older Family Diagram; open it in the current desktop app and save it again.");
  expect(await bring(new File(["junk"], "Lund family.fd"))).toBe(
    "That file was saved by an older Family Diagram; open it in the current desktop app and save it again.",
  );
  answering(413, "<html><body><h1>413 Request Entity Too Large</h1></body></html>");
  expect(await bring(new File(["junk"], "Lund family.fd"))).toBe("Could not bring in the file.");
  expect(refusal(new File([new Uint8Array(20 * 1024 * 1024 + 1)], "Lund family.zip"))).toBe(TOO_BIG);
  expect(refusal(new File(["PK"], "Lund family.zip"))).toBeNull();
});

// R-0899
it("offers the import row to a reader without a professional licence", () => {
  const made: { className: string; innerHTML?: string }[] = [];
  vi.stubGlobal("document", {
    createElement: () => {
      const node = { className: "", dataset: {}, append() {}, addEventListener() {}, setAttribute() {} };
      made.push(node);
      return node;
    },
  });
  const page = { addEventListener() {} } as unknown as HTMLElement;
  expect(Importer.prototype.row.call({}, page).className).toBe("sn-row push");
  expect(made.map((one) => one.innerHTML)).toContain("Import a Family Diagram file");
  expect(made.map((one) => one.innerHTML)).toContain("or a .zip of it");
});

