import { describe, expect, it, vi } from "vitest";

vi.stubGlobal("window", {
  BOOTSTRAP: { user: { username: "c", admin: false, pro: false, coder: true } },
});

const { Coding, writtenConcepts } = await import("../src/coding");

/** The sheet that asks a coder to finish, drawn by the screen's own code on
 * stand-ins for the elements it writes into. */
function finishSheet(): string {
  const node = () => ({ innerHTML: "", hidden: true, offsetWidth: 0, classList: { add() {} } });
  const screen = {
    thread: { session: "Marcus", cut_day: "Sep 4", meeting_date: "2026-09-25" },
    sheet: node(),
    scrim: node(),
  };
  Coding.prototype.confirm.call(screen as unknown as InstanceType<typeof Coding>);
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
      [event(7, { anxiety: "up", relationship: "distance" }), event(8, { symptom: "up" })],
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
    type Node = { dataset: Record<string, string>; innerHTML: string; className: string };
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
            said: [{ text: "mom anxious", lines: ["+ Mom · shift · 1971"], event_ids: [7] }],
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
                insertAdjacentHTML: (_: string, html: string) => (node.innerHTML += html),
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
});
