import { describe, expect, it, vi } from "vitest";

vi.mock("../src/api", async (real) => ({
  ...(await real<typeof import("../src/api")>()),
  scribe: vi.fn(),
}));

vi.stubGlobal("window", {
  BOOTSTRAP: { user: { username: "c", admin: false, pro: false, coder: true } },
});

const { Coding, scribedRows, writtenConcepts } = await import("../src/coding");
const api = await import("../src/api");
const { Failed } = api;
const { Menu } = await import("../src/menu");
const { HAND_EDITS } = await import("../src/editor");
const { standInForm } = await import("./standin");

/** The sheet that asks a coder to finish, drawn by the screen's own code on
 * stand-ins for the elements it writes into. */
function finishSheet(): string {
  const node = () => ({
    innerHTML: "",
    hidden: true,
    offsetWidth: 0,
    classList: { add() {} },
  });
  const screen = {
    thread: { session: "Marcus", cut_day: "Sep 4", meeting_date: "2026-09-25" },
    sheet: node(),
    scrim: node(),
  };
  Coding.prototype.confirm.call(
    screen as unknown as InstanceType<typeof Coding>,
  );
  return screen.sheet.innerHTML;
}

describe("the finish sheet", () => {
  // R-0315
  it.fails("names the other coders' versions as opinions", () => {
    // Known defect: the sheet still says the other coders' takes.
    const words = finishSheet();
    expect(words).toContain("Finish coding?");
    expect(words).not.toMatch(/\btakes?\b/);
    expect(words).toMatch(/\bopinions\b/);
  });
});

describe("the concept pages under what the scribe wrote", () => {
  const event = (id: number, fields: object) => ({ id, ...fields }) as never;

  // R-0541
  it("links each code the new events carry to its page, one tap away", () => {
    const html = writtenConcepts(
      [7],
      [
        event(7, { anxiety: "up", relationship: "distance" }),
        event(8, { symptom: "up" }),
      ],
    );
    expect(html).toContain('href="/app/theory/anxiety"');
    expect(html).toContain('href="/app/theory/distance"');
    expect(html).not.toContain("symptom");
  });

  // R-0541
  it("adds nothing when what was written carries no code", () => {
    expect(writtenConcepts([], [event(7, { anxiety: "up" })])).toBe("");
  });

  // R-0541
  it("hangs the pages under lines written before the coding was reopened", () => {
    type Node = {
      dataset: Record<string, string>;
      innerHTML: string;
      className: string;
    };
    const nodes: Node[] = [];
    vi.stubGlobal("document", {
      createElement: () => ({ dataset: {}, innerHTML: "", className: "" }),
    });
    const screen = Object.assign(Object.create(Coding.prototype), {
      thread: {
        agreed: null,
        turns: [
          {
            id: 3,
            client: true,
            text: "She stopped sleeping",
            above: false,
            said: [
              {
                text: "mom anxious",
                lines: [{ verb: "add", text: "Mom · shift · 1971" }],
                event_ids: [7],
              },
            ],
          },
        ],
      },
      timeline: { events: [event(7, { anxiety: "up" })] },
      list: {
        set innerHTML(_: string) {
          nodes.length = 0;
        },
        append: (node: Node) => nodes.push(node),
        querySelectorAll: () =>
          nodes
            .filter((node) => node.dataset.events)
            .map((node) =>
              Object.assign(node, {
                querySelector: () => null,
                insertAdjacentHTML: (_: string, html: string) =>
                  (node.innerHTML += html),
              }),
            ),
      },
      cutline: () => ({ dataset: {}, innerHTML: "", className: "" }),
      paint: () => {},
      toEnd: () => {},
    });
    screen.render();
    screen.paintConcepts();
    vi.unstubAllGlobals();
    const line = nodes.find((node) => node.innerHTML.includes("Mom"));
    expect(line?.innerHTML).toContain('href="/app/theory/anxiety"');
  });

  // R-0883
  it("rebuilds one statement's rows in one bubble, verb first, and a statement that saved nothing as its muted row", () => {
    const nodes: {
      innerHTML: string;
      className: string;
      dataset: Record<string, string>;
    }[] = [];
    vi.stubGlobal("document", {
      createElement: () => ({ dataset: {}, innerHTML: "", className: "" }),
    });
    const screen = Object.assign(Object.create(Coding.prototype), {
      thread: {
        agreed: null,
        turns: [
          {
            id: 3,
            client: true,
            text: "She married Tom",
            above: false,
            said: [
              {
                text: "Ann married Tom",
                lines: [
                  { verb: "add", text: "Tom" },
                  { verb: "change", text: "Ann & Tom · Married · 1970" },
                ],
                event_ids: [7],
              },
              { text: "she left", lines: [], event_ids: [] },
            ],
          },
        ],
      },
      list: {
        set innerHTML(_: string) {
          nodes.length = 0;
        },
        append: (node: (typeof nodes)[number]) => nodes.push(node),
      },
      cutline: () => ({ dataset: {}, innerHTML: "", className: "" }),
      paint: () => {},
      toEnd: () => {},
    });
    screen.render();
    vi.unstubAllGlobals();
    vi.stubGlobal("window", {
      BOOTSTRAP: {
        user: { username: "c", admin: false, pro: false, coder: true },
      },
    });
    const rows = nodes.filter((node) =>
      node.className.startsWith("bub coach sub"),
    );
    expect(rows.map((node) => node.innerHTML)).toEqual([
      '<div class="did">Added <em>Tom</em></div>' +
        '<div class="did">Changed <em>Ann &amp; Tom · Married · 1970</em></div>',
      '<div class="did no">nothing saved</div>',
    ]);
    expect(rows[0].dataset.events).toBe("7");
  });
});

describe("what a coder reads when a statement did not go in", () => {
  // R-0869, R-0883
  it("is one muted row whatever the server answered, never its words", async () => {
    vi.stubGlobal("document", {
      createElement: () => ({
        className: "",
        innerHTML: "",
        dataset: {},
        remove() {},
      }),
    });
    const drawn: { innerHTML: string; className: string }[] = [];
    const screen = Object.assign(Object.create(Coding.prototype), {
      thread: { coding_id: 9, turns: [{ id: 3, client: true }] },
      picture: { untouch() {} },
      after: (_turn: number, node: { innerHTML: string; className: string }) =>
        drawn.push(node),
      refresh: async () => {},
    });
    const scribe = vi.mocked(api.scribe);
    for (const failed of [
      new Failed(
        400,
        "POST /scribe",
        "that turn is not part of this conversation",
      ),
      new Failed(500, "POST /scribe", "Traceback"),
      new Failed(0, "POST /scribe", "timed out"),
    ]) {
      scribe.mockRejectedValueOnce(failed);
      await screen.scribe(3, "Marcus could not sleep", null);
    }
    vi.unstubAllGlobals();
    vi.stubGlobal("window", {
      BOOTSTRAP: {
        user: { username: "c", admin: false, pro: false, coder: true },
      },
    });
    expect(
      drawn
        .filter((node) => !node.className.includes("typing"))
        .map((node) => node.innerHTML),
    ).toEqual(Array(3).fill('<div class="did no">not saved, try again</div>'));
  });
});

describe("the rows under what the coder said", () => {
  const scribed = (fields: object) =>
    ({
      lines: [],
      refused: [],
      choices: [],
      made: [],
      turn_id: "t",
      ...fields,
    }) as never;

  // R-0883
  it("draws a row for each entry that went in and a muted one for each refused, verb first as the chat does", () => {
    const html = scribedRows(
      scribed({
        lines: [
          { verb: "add", text: "James Cooper" },
          { verb: "change", text: "Marcus" },
        ],
        refused: [{ verb: "add", text: "Marcus · could not sleep · Jan 2010" }],
      }),
    );
    expect(html).toBe(
      '<div class="did">Added <em>James Cooper</em></div>' +
        '<div class="did">Changed <em>Marcus</em></div>' +
        '<div class="did no">Tried to add <em>Marcus · could not sleep · Jan 2010</em>. Not saved</div>',
    );
  });

  // R-0883
  it("is one muted row when nothing was saved", () => {
    expect(scribedRows(scribed({}))).toBe(
      '<div class="did no">nothing saved</div>',
    );
  });

  // R-0883
  it("asks who is meant when the people do not share a first name", () => {
    expect(
      scribedRows(
        scribed({
          choices: [
            { id: 1, name: "Robert Smith" },
            { id: 2, name: "James Smith" },
          ],
        }),
      ),
    ).toContain('<div class="did ask">Who is this about?</div>');
  });

  // R-0883
  it("offers one button per person and a tap sends the same words with that person", async () => {
    type Node = {
      className: string;
      innerHTML: string;
      dataset: Record<string, string>;
      click?: (e: object) => void;
      addEventListener(type: string, fn: (e: object) => void): void;
      remove(): void;
    };
    const drawn: Node[] = [];
    vi.stubGlobal("document", {
      createElement: (): Node => ({
        className: "",
        innerHTML: "",
        dataset: {},
        addEventListener(_, fn) {
          this.click = fn;
        },
        remove() {},
      }),
    });
    const scribe = vi.mocked(api.scribe);
    scribe.mockResolvedValueOnce(
      scribed({
        choices: [
          { id: 1, name: "Marcus Smith" },
          { id: 2, name: "Marcus Jones" },
        ],
      }),
    );
    scribe.mockResolvedValueOnce(
      scribed({
        lines: [
          { verb: "add", text: "Marcus Jones · Could not sleep · Jan 2010" },
        ],
      }),
    );
    const screen = Object.assign(Object.create(Coding.prototype), {
      thread: { coding_id: 9, turns: [{ id: 3, client: true }] },
      picture: { untouch() {} },
      after: (_turn: number, node: Node) => drawn.push(node),
    });
    await screen.scribe(3, "Marcus could not sleep", null);
    const answers = () =>
      drawn.filter((node) => !node.className.includes("typing"));
    expect(answers()[0].innerHTML).toBe(
      '<div class="did ask">Which Marcus do you mean?</div>' +
        '<button class="did pick" type="button" data-person="1">Marcus Smith</button>' +
        '<button class="did pick" type="button" data-person="2">Marcus Jones</button>',
    );
    answers()[0].click!({
      target: { closest: () => ({ dataset: { person: "2" } }) },
    });
    await vi.waitFor(() => expect(answers()).toHaveLength(2));
    vi.unstubAllGlobals();
    vi.stubGlobal("window", {
      BOOTSTRAP: {
        user: { username: "c", admin: false, pro: false, coder: true },
      },
    });
    expect(scribe.mock.lastCall).toEqual([9, 3, "Marcus could not sleep", 2]);
    expect(answers()[1].innerHTML).toBe(
      '<div class="did">Added <em>Marcus Jones · Could not sleep · Jan 2010</em></div>',
    );
  });

  // R-0883, R-0636
  it("shows the chat's three dots where the rows will be from the send until the answer lands", async () => {
    type Node = {
      className: string;
      innerHTML: string;
      dataset: Record<string, string>;
      gone?: boolean;
    };
    vi.stubGlobal("document", {
      createElement: (): Node =>
        ({
          className: "",
          innerHTML: "",
          dataset: {},
          addEventListener() {},
          remove(this: Node) {
            this.gone = true;
          },
        }) as Node,
    });
    let answer!: (value: never) => void;
    vi.mocked(api.scribe).mockReturnValueOnce(
      new Promise((done) => (answer = done)),
    );
    const drawn: Node[] = [];
    const screen = Object.assign(Object.create(Coding.prototype), {
      thread: { coding_id: 9, turns: [{ id: 3, client: false }] },
      picture: { untouch() {} },
      after: (_turn: number, node: Node) => drawn.push(node),
    });
    const sent = screen.scribe(3, "Marcus could not sleep", null);
    expect(drawn.map((node) => node.className)).toEqual([
      "bub coach typing wait sub left",
    ]);
    expect(drawn[0].innerHTML).toBe('<span class="words"></span>');
    expect(drawn[0].gone).toBeUndefined();
    answer(scribed({ lines: [{ verb: "add", text: "Marcus" }] }));
    await sent;
    vi.unstubAllGlobals();
    vi.stubGlobal("window", {
      BOOTSTRAP: {
        user: { username: "c", admin: false, pro: false, coder: true },
      },
    });
    expect(drawn[0].gone).toBe(true);
    expect(drawn[1].innerHTML).toBe(
      '<div class="did">Added <em>Marcus</em></div>',
    );
  });
});

describe("the lines across the thread", () => {
  const label = (now: boolean) =>
    (
      Coding.prototype as unknown as {
        cutline(thread: object, now: boolean): { innerHTML: string };
      }
    ).cutline(
      {
        turns: [{ order: 42 }],
        cut_day: "Oct 12",
        agreed: { order: 30, ratified: "Oct 5" },
      },
      now,
    ).innerHTML;

  // R-0869
  it("say where the cut is and when it was ratified, never a turn number", () => {
    vi.stubGlobal("document", {
      createElement: () => ({ dataset: {}, innerHTML: "", className: "" }),
    });
    const here = label(true);
    const last = label(false);
    vi.unstubAllGlobals();
    vi.stubGlobal("window", {
      BOOTSTRAP: {
        user: { username: "c", admin: false, pro: false, coder: true },
      },
    });
    expect(here).toContain("cut here · Oct 12");
    expect(last).toContain("last cut · ratified Oct 5");
    expect(here + last).not.toMatch(/turn|42|30/);
  });
});

describe("the drawer's forms", () => {
  type Held = { held(form: HTMLElement): HTMLElement };
  const menu = (detail?: object) =>
    new Menu({} as HTMLElement, async () => ({}) as never, () => 1, detail as never);

  // R-0887
  it("are read only on the coding screen and in the personal app alike", () => {
    expect(HAND_EDITS).toBe(false);
    for (const one of [menu(), menu({})]) {
      const form = standInForm();
      (one as unknown as Held).held(form as unknown as HTMLElement);
      expect(form.acts.removed).toBe(true);
      expect(form.fields.every((field) => field.readOnly)).toBe(true);
      expect(form.picks.every((pick) => pick.disabled)).toBe(true);
    }
  });

  // R-0271
  it("read the coding's own submitted state", () => {
    const finished = (done_at: string | null) =>
      Coding.prototype.finished.call({
        thread: { done_at },
      } as unknown as InstanceType<typeof Coding>);
    expect(finished("2026-10-19")).toBe(true);
    expect(finished(null)).toBe(false);
  });
});
