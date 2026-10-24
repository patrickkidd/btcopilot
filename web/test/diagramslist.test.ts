import { afterEach, expect, it, vi } from "vitest";

vi.stubGlobal("window", {
  BOOTSTRAP: { user: { username: "ann", pro: true } },
  setTimeout: (run: () => void) => run(),
});

const { Asked, Page, Settings, SWIPED } = await import("../src/settings");
const { store } = await import("../src/store");

afterEach(() => vi.unstubAllGlobals());

/** The toasts the page shows, by their words. */
function toasts(): () => string[] {
  const made: { className: string; textContent: string }[] = [];
  vi.stubGlobal("document", {
    querySelector: () => ({ append() {}, content: "served" }),
    createElement: () => {
      const node = { className: "", textContent: "", classList: { add() {}, remove() {} }, append() {}, remove() {} };
      made.push(node);
      return node;
    },
  });
  vi.stubGlobal("window", { setTimeout: () => 0, clearTimeout() {} });
  return () => made.filter((one) => one.className === "toast").map((one) => one.textContent);
}

const lund = { id: 7, name: "Lund family" };
const reyes = { id: 8, name: "Reyes family" };

/** The account view with only what showing a page touches: a page drawn is
 * counted, and the diagrams the server answers are the ones given. */
function view(listed: object[], answered: object[]) {
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ diagrams: answered }), { status: 200 }));
  const pane = () => ({ classList: { add() {}, remove() {} }, dataset: {}, addEventListener() {}, remove() {}, offsetWidth: 0 });
  const drawn: string[] = [];
  const settings = Object.assign(Object.create(Settings.prototype), {
    open: true,
    stack: [{ page: Page.Root, title: "Account", pane: pane() }],
    account: { diagrams: listed },
    host: { append() {} },
    back: {},
    handlers: { onTitle() {} },
    build: (page: string) => {
      drawn.push(page);
      return { title: page, pane: pane() };
    },
  });
  return { settings, drawn };
}

// R-0899
it("reads the diagrams again each time their page is shown and draws it again when one has come in", async () => {
  const { settings, drawn } = view([lund], [lund, reyes]);
  settings.push(Page.Diagrams);
  await vi.waitFor(() => expect(drawn).toEqual([Page.Diagrams, Page.Diagrams]));
  expect(settings.account.diagrams).toEqual([lund, reyes]);
});

// R-0899
it("leaves the page as drawn when the diagrams are the same", async () => {
  const { settings, drawn } = view([lund], [lund]);
  await settings.relist();
  settings.stack.push({ page: Page.Diagrams, title: "Diagrams", pane: {} });
  await settings.relist();
  expect(drawn).toEqual([]);
});

// R-0899
it("opens a diagram made from a desktop file the way a tap in the list does, with no toast over the sheet that follows", async () => {
  const { settings } = view([lund], [lund, reyes]);
  const opened: unknown[] = [];
  settings.handlers.onOpen = async (...args: unknown[]) => void opened.push(args);
  settings.close = () => (settings.open = false);
  settings.load = async () => {};
  const said = toasts();
  const made = { ...reyes, imported: { people: 41, events: 212, left_out: 0 } };
  await settings.imported(made);
  expect(settings.open).toBe(false);
  expect(opened).toEqual([[reyes.id]]);
  expect(said()).toEqual([]);
});

const own = (id: number, name: string, free = false) => ({
  id,
  name,
  session_count: 2,
  last_activity: null,
  free,
  owned: true,
  access: "own",
  owner: "Ann Lund",
  owner_name: "Ann Lund",
});

// R-0904
it("offers no swipe to delete on the free diagram's row", () => {
  vi.stubGlobal("document", {
    createElement: () => ({ dataset: {}, className: "", append() {}, addEventListener() {} }),
  });
  const row = (diagram: ReturnType<typeof own>) =>
    Settings.prototype["diagramRow"].call({ pressToRename() {} }, diagram as never, new Date());
  expect(row(own(1, "Ann's family", true)).dataset).toHaveProperty("free");
  expect(row(own(8, "Reyes family")).dataset).not.toHaveProperty("free");
  expect(SWIPED).toContain(":not([data-free])");
});

/** The server deleting a diagram and listing what is left. */
function deleting(left: object[], refused: Response | null = null) {
  const asked: string[] = [];
  const said = toasts();
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    asked.push(`${init.method} ${url}`);
    if (init.method !== "DELETE") return new Response(JSON.stringify(left), { status: 200 });
    return refused ?? new Response(null, { status: 204 });
  });
  const switched: object[] = [];
  const removed: string[] = [];
  const settings = Object.assign(Object.create(Settings.prototype), {
    account: { diagrams: [own(1, "Ann's family", true), own(8, "Reyes family")] },
    switchTo: async (diagram: object) => void switched.push(diagram),
  });
  const marks = new Set<string>();
  const row = {
    dataset: { diagram: "8" },
    remove: () => void removed.push("8"),
    classList: {
      contains: (name: string) => marks.has(name),
      add: (name: string) => void marks.add(name),
      remove: (name: string) => void marks.delete(name),
    },
  };
  return { asked, switched, removed, settings, row, said };
}

// R-0904, R-0908
it("deletes a swiped diagram's row, and goes to the free diagram when it was the one open", async () => {
  const away = deleting([own(1, "Ann's family", true)]);
  vi.spyOn(store, "current").mockReturnValue({ diagram: { id: 1 } } as never);
  await away.settings.drop(away.row);
  expect([away.asked, away.removed, away.switched]).toEqual([["DELETE /app/diagrams/8"], ["8"], []]);
  expect(away.settings.account.diagrams.map((one: { id: number }) => one.id)).toEqual([1]);

  const open = deleting([own(1, "Ann's family", true)]);
  vi.spyOn(store, "current").mockReturnValue({ diagram: { id: 8 } } as never);
  await open.settings.drop(open.row);
  expect(open.asked).toEqual(["DELETE /app/diagrams/8", "GET /app/diagrams"]);
  expect(open.switched).toEqual([own(1, "Ann's family", true)]);
});

// R-0904
it("says a refusal once, in the server's sentence when it is one and in plain words when it is a page", async () => {
  const page = deleting([], new Response("<!doctype html><html><body><h1>Not Found</h1></body></html>", { status: 404 }));
  vi.spyOn(store, "current").mockReturnValue({ diagram: { id: 1 } } as never);
  await Promise.all([page.settings.drop(page.row), page.settings.drop(page.row)]);
  expect([page.asked, page.said(), page.removed]).toEqual([["DELETE /app/diagrams/8"], ["Could not delete the diagram."], []]);

  const free = deleting([], new Response("Your personal diagram cannot be deleted.", { status: 400 }));
  await free.settings.drop(free.row);
  expect(free.said()).toEqual(["Your personal diagram cannot be deleted."]);
});

// R-0904
it("asks under the diagram's name before deleting it, and only its Delete sends the request", () => {
  const shown: string[] = [];
  const dropped: unknown[] = [];
  const settings = Object.assign(Object.create(Settings.prototype), {
    account: { diagrams: [own(1, "Ann's family", true), own(8, "Reyes family")] },
    ask: { show: (html: string) => void shown.push(html), lower() {} },
    drop: async (row: unknown) => void dropped.push(row),
  });
  const row = { dataset: { diagram: "8" } };
  settings.askDrop(row);
  expect(shown[0]).toContain("Delete Reyes family?");
  expect(shown[0]).toContain("It is hidden from you; nothing is erased.");
  expect(shown[0]).toContain(`data-act="${Asked.Delete}">Delete<`);
  expect(shown[0]).toContain(`data-act="${Asked.Cancel}">Cancel<`);
  settings.answer(Asked.Cancel);
  expect(dropped).toEqual([]);
  settings.askDrop(row);
  settings.answer(Asked.Delete);
  expect(dropped).toEqual([row]);
});
