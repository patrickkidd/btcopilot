import { describe, expect, it, vi } from "vitest";

vi.mock("../src/api", async (real) => ({
  ...(await real<typeof import("../src/api")>()),
  scribe: vi.fn(),
}));

vi.stubGlobal("window", {
  BOOTSTRAP: { user: { username: "c", admin: false, pro: false, coder: true } },
});

const { Coding, Resume, given, line, resumeAt, scribedRows, writtenConcepts } =
  await import("../src/coding");
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
    });
    screen.render();
    screen.paintConcepts();
    vi.unstubAllGlobals();
    const line = nodes.find((node) => node.innerHTML.includes("Mom"));
    expect(line?.innerHTML).toContain('href="/app/theory/anxiety"');
  });

  // R-0883, R-0942
  it("rebuilds one statement's rows in one bubble, verb first, a statement that saved nothing as its muted row, and the scribe's words as their row", () => {
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
                reply: "",
              },
              { text: "she left", lines: [], event_ids: [], reply: "" },
              {
                text: "do we have her birth yet?",
                lines: [],
                event_ids: [],
                reply: "Not yet.",
              },
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
      '<div class="did ask">Not yet.</div>',
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
      reply: "",
      ...fields,
    }) as never;

  // R-0942
  it("shows the scribe's words as the row its question to pick a person is", () => {
    expect(scribedRows(scribed({ reply: "Not yet. Who told you?" }))).toBe(
      '<div class="did ask">Not yet. Who told you?</div>',
    );
  });

  // R-0942
  it("puts the scribe's words under the rows it wrote", () => {
    expect(
      scribedRows(
        scribed({
          lines: [{ verb: "add", text: "Ann · Birth · 1950" }],
          reply: "Added her birth.",
        }),
      ),
    ).toBe(
      '<div class="did">Added <em>Ann · Birth · 1950</em></div>' +
        '<div class="did ask">Added her birth.</div>',
    );
  });

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

describe("the given facts at the top of the thread", () => {
  const person = (fields: object) =>
    ({
      id: 1,
      name: "Ann",
      last_name: "Cole",
      primary: false,
      birth_event: null,
      ...fields,
    }) as never;
  const copy = (people: never[], events: object[] = []) =>
    ({ people, events }) as never;

  // R-0940
  it("name the subject and their birth as the drawer dates it", () => {
    const events = [
      { id: 5, dateTime: "1950-03-03", datePrecision: "day" },
    ];
    expect(
      given(
        copy([person({ primary: true, birth_event: 5 }), person({ id: 2 })], events),
        true,
      ),
    ).toBe("Given: Ann Cole, born 3 Mar 1950");
    expect(given(copy([person({ birth_event: 5 })], events), false)).toBe(
      "Given: Ann Cole, born 3 Mar 1950",
    );
  });

  // R-0940
  it("name the subject alone when the copy holds no birth for them", () => {
    expect(given(copy([person({ primary: true })]), false)).toBe(
      "Given: Ann Cole",
    );
  });

  // R-0940
  it("are not there when the copy is empty", () => {
    expect(given(copy([]), false)).toBe("");
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
    new Menu({ addEventListener() {} } as unknown as HTMLElement, async () => ({}) as never, () => 1, detail as never);

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

describe("a line of the conversation being coded", () => {
  // R-0072, R-0270
  it("is drawn as the chat draws the coach's markup, never as brackets", () => {
    const html = line({ client: false, text: "That sounds hard. When did it start? [[ask:high school years]]" });
    expect(html).not.toContain("[[");
    expect(html).toContain('<div class="ask">When did it start?</div>');
    expect(html).toContain('<div class="offer"><button type="button" class="chip ask" data-kind="ask"');
    expect(html).toContain(">[high school years]</button>");
  });

  // R-0072, R-0270
  it("keeps a client's words as written, a chip they sent back drawn as one", () => {
    const html = line({ client: true, text: "It was [[event:7|Dad left]] that year." });
    expect(html).not.toContain("[[");
    expect(html).toContain(">Dad left</button> that year.");
  });
});

describe("where the coding screen opens", () => {
  const turn = (id: number, coded: boolean, above = false) => ({
    id,
    order: id,
    who: "",
    client: true,
    text: "",
    above,
    said: coded ? [{ text: "x", lines: [], event_ids: [], reply: "" }] : [],
  });
  const thread = (turns: ReturnType<typeof turn>[], agreed = false) =>
    ({
      turns,
      agreed: agreed ? { order: 2, day: "Sep 1", ratified: "Sep 3" } : null,
    }) as unknown as Parameters<typeof resumeAt>[0];

  // R-0265
  it("opens on the line after the last one the coder coded", () => {
    expect(resumeAt(thread([turn(1, true), turn(2, false), turn(3, true), turn(4, false), turn(5, false)]))).toBe(4);
  });

  // R-0265
  it("opens where coding starts when nothing is coded yet", () => {
    expect(resumeAt(thread([turn(1, false), turn(2, false)]))).toBe(Resume.Top);
    expect(resumeAt(thread([turn(1, false, true), turn(2, false, true), turn(3, false)], true))).toBe(3);
  });

  // R-0265
  it("opens on the last line when every line is coded", () => {
    expect(resumeAt(thread([turn(1, true), turn(2, true)]))).toBe(Resume.End);
  });
});
