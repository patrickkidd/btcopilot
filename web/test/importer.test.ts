import { afterEach, expect, it, vi } from "vitest";
import type { Person } from "../src/types";

vi.stubGlobal("window", { BOOTSTRAP: { user: { username: "ann", pro: false } } });

const { Part, store } = await import("../src/store");
const { ADD_CODES, Answer, awaitClusters, Pick, bring, fromDrop, fromPicked, Importer, PICKLE, refusal, TOO_BIG } = await import(
  "../src/importer"
);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

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

const lund = { id: 9, name: "Lund family", imported: { people: 4, events: 212, left_out: 3, primary: [12, 11] } };

const person = (id: number, name: string, last_name: string | null = "Lund") => ({ id, name, last_name }) as Person;
const people = [person(10, "Walter"), person(11, "Ann"), person(12, "Karen"), person(13, "Tomas", null)];

/** The importer with its sheet and what it hands on recorded, on a diagram
 * whose people are already in the page. */
const importer = (made: object | null = lund) => {
  const done = { opened: [] as unknown[], said: [] as string[], shown: [] as string[], lowered: 0, stored: [] as unknown[] };
  // clusters already in, so an import's wait for them ends at once
  vi.spyOn(store, "current").mockReturnValue({ record: { people, clusters: [{ id: "c1" }] } } as never);
  vi.spyOn(store, "update").mockImplementation((fresh) => void done.stored.push(fresh));
  const one = Object.assign(Object.create(Importer.prototype), {
    sending: false,
    made,
    opened: async (made: unknown) => void done.opened.push(made),
    say: (words: string) => void done.said.push(words),
    sheet: { show: (html: string) => void done.shown.push(html), lower: () => void done.lowered++ },
  });
  return { one, done };
};

const asked = "Should the coach go through the events and add codes where the file has none?";

// R-0899, R-0902, R-0905
it("opens the new diagram and then says how much of the file came in and asks whose family it is", async () => {
  const sent = answering(201, JSON.stringify(lund));
  const { one, done } = importer(null);
  await one.send(new File(["\x80\x03}q"], "Lund family.fd.zip"));
  expect([sent[0].get("name"), sent[0].has("coding")]).toEqual(["Lund family", false]);
  expect(done.opened).toEqual([lund]);
  expect(done.shown[0]).toContain("Your file is in: 4 people and 212 events.");
  expect(done.shown[0]).toContain("3 could not be brought in; the coach will ask about them.");
  expect(done.shown[0]).toContain("Is this your own family?");
  expect(done.shown[0]).not.toContain(asked);
});

const listed = (html: string, pick: string) =>
  [...html.matchAll(new RegExp(`class="sn-row push[^"]*" type="button" data-${pick}="(\\d+)"`, "g"))].map((match) => Number(match[1]));

// R-0899, R-0930
it("asks who the case is about when it is not the person's own family, with no question of which one they are", () => {
  const { one, done } = importer();
  one.answer(Answer.NotOwn);
  expect(done.shown[0]).toContain("Who is this case about?");
  expect(done.shown[0]).not.toContain("Which person are you?");
  expect(done.shown[0]).not.toContain(asked);
  expect(listed(done.shown[0], Pick.About)).toEqual([12, 11, 10, 13]);
  expect(done.shown[0]).toContain("Your file is in: 4 people and 212 events.");
});

// R-0899, R-0930
it("lists the file's primary people first when it is the person's own family", () => {
  const { one, done } = importer();
  one.answer(Answer.Own);
  expect(listed(done.shown[0], Pick.Me)).toEqual([12, 11, 10, 13]);
  expect(done.shown[0]).toContain("Which person are you?");
  expect(done.shown[0]).toContain(">Karen Lund<");
  expect(done.shown[0]).toContain(">Tomas<");
  expect(done.shown[0]).not.toContain("Go on with");
});

// R-0930
it("comes with the file's one primary person picked, ready to go on with", () => {
  const { one, done } = importer({ ...lund, imported: { ...lund.imported, primary: [11] } });
  one.answer(Answer.NotOwn);
  expect(done.shown[0]).toContain('class="sn-row push cur" type="button" data-about="11"');
  expect(done.shown[0]).toContain('<button class="cf-go" type="button" data-about="11">Go on with Ann Lund</button>');
});

/** The server taking a pick, and what it was sent. */
function picks() {
  const sent: string[] = [];
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    sent.push(`${init.method} ${url} ${init.body}`);
    return new Response(JSON.stringify({ ...lund, person_id: 12 }), { status: 200 });
  });
  return sent;
}

// R-0899, R-0930
it("says who the person is in the diagram when they pick their name, then asks about codes", async () => {
  const sent = picks();
  const { one, done } = importer();
  const read = vi.spyOn(store, "refresh").mockResolvedValue(true);
  await one.choose(Pick.Me, 12);
  expect(sent).toEqual(['PATCH /app/diagrams/9/access {"person_id":12}']);
  expect(done.stored).toEqual([{ diagram: { ...lund, person_id: 12 } }]);
  expect(read).toHaveBeenCalledWith(Part.Record);
  expect(done.shown[0]).toContain(asked);
});

// R-0899, R-0930
it("makes the person picked the one the case is about, then asks about codes", async () => {
  const sent = picks();
  const { one, done } = importer();
  const read = vi.spyOn(store, "refresh").mockResolvedValue(true);
  await one.choose(Pick.About, 11);
  expect(sent).toEqual(['PATCH /app/people/11?diagram_id=9 {"primary":true}']);
  expect(read).toHaveBeenCalledWith(Part.Record);
  expect(done.shown[0]).toContain(asked);
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


/** The record as the server answers it on each read, one answer per read. */
function reads(...answers: object[]) {
  const asked: string[] = [];
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  vi.stubGlobal("fetch", async (url: string) => {
    asked.push(url);
    return new Response(JSON.stringify(answers.shift()), { status: 200 });
  });
  return asked;
}

const bare = { people, clusters: [] as object[] };
const grouped = { people, clusters: [{ id: "c1", event_ids: [4, 5, 6] }] };

// R-0899
it("reads the new diagram's record again every 5 seconds until its clusters come in, drawing it only when it changed", async () => {
  let opened = { record: bare };
  const drawn: object[] = [];
  vi.spyOn(store, "current").mockImplementation(() => opened as never);
  vi.spyOn(store, "update").mockImplementation((fresh) => {
    drawn.push(fresh);
    opened = { ...opened, ...(fresh as { record: typeof bare }) };
  });
  const asked = reads(bare, grouped);
  const waited: number[] = [];
  await awaitClusters(async (ms) => void waited.push(ms), () => 0);
  expect(waited).toEqual([5000, 5000]);
  expect(asked).toHaveLength(2);
  expect(drawn).toEqual([{ record: grouped }]);
});

// R-0899
it("stops reading after 3 minutes, and as soon as another diagram is opened", async () => {
  vi.spyOn(store, "current").mockReturnValue({ record: bare } as never);
  vi.spyOn(store, "update").mockImplementation(() => {});
  let clock = 0;
  const asked = reads(...Array(40).fill(bare));
  await awaitClusters(async (ms) => void (clock += ms), () => clock);
  expect(asked).toHaveLength(36);

  vi.spyOn(store, "fetch").mockResolvedValue(null);
  const waited: number[] = [];
  await awaitClusters(async (ms) => void waited.push(ms), () => 0);
  expect(waited).toEqual([5000]);
});
