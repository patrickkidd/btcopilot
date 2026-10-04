import { expect, test } from "@playwright/test";
import { addForm, boxOf, inside, openList, pinned, stateFor, steady, type Key } from "./setup";

/** What the resting picture looks like on each shape of record, and what a tap
 * on it does. Goldens, so a change to the drawing has to be looked at.
 *
 * Held to the strict count rather than the suite's one percent: a percent of
 * this picture is hundreds of pixels, enough to hide a box becoming a bare dot,
 * which is exactly what it did hide once. */

const settle = async (page: import("@playwright/test").Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(400);
};

const picture = (page: import("@playwright/test").Page) => page.locator("#chat-screen .pic");

test.describe("the resting picture", () => {
  for (const [key, what] of [
    ["empty", "nothing has a date yet"],
    ["one", "one moment"],
    ["three40", "three moments over forty years"],
    ["dense60", "sixty moments in five years"],
  ] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });
      // R-0416
      test(`at rest: ${what}`, async ({ page }) => {
        await settle(page);
        await expect(picture(page)).toHaveScreenshot(`rest-${key}.png`, steady(page));
      });
    });
  }
});

/** The picture opens at rest showing the whole line, so a test about the wire
 * has to open a cluster first, which is what a reader does. */
const openCluster = async (page: import("@playwright/test").Page) => {
  await page.locator('.ss-hit[data-target="cluster"]').first().click();
  await expect(page.locator('#path [data-step="0"]')).toBeVisible();
  await page.waitForTimeout(400);
};

test.describe("a tap on a cluster", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0416
  test("opens it, and the wire underneath is tappable", async ({ page }) => {
    await settle(page);
    await expect(page.locator('.ss-hit[data-target="cluster"]').first()).toBeVisible();
    await openCluster(page);
    await expect(picture(page)).toHaveScreenshot("cluster-open.png", steady(page));
  });
});

test.describe("a tap on the wire", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0073
  test("picks the moment under it and writes it out", async ({ page }) => {
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(page.locator("#view .ss-t.on").first()).toBeVisible();
    await expect(page.locator("#view .ss-t.on").first()).not.toBeEmpty();
    await inside(page.locator("#view .ss-t.on").first(), picture(page));
  });

  // R-0072, R-0055
  test("the chip beside it drops a reference in the composer", async ({ page }) => {
    test.fixme(true, "the ask chip is hidden for now (Patrick, 2026-09-29)");
    await settle(page);
    await openCluster(page);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await page.locator("#cap-chip").click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await expect(page.locator("#composer .chip")).not.toBeEmpty();
    await inside(page.locator("#composer .chip"), page.locator("#chat-screen .inbar"));
  });
});

test.describe("the undated shelf", () => {
  test.use({ storageState: stateFor("empty") });

  // R-0359, R-0013
  test("is not drawn on the picture at all", async ({ page }) => {
    await settle(page);
    // Both question marks are off (R-0359): nothing told a first-time reader
    // what they meant. The shelf itself stays, reached from the events list,
    // so the picture offers no way to tap it and no mark to read.
    await expect(page.locator('#view .ss-hit[data-target="shelf"]')).toHaveCount(0);
    await expect(page.locator("#view .qm")).toHaveCount(0);
  });
});

/** A long record is drawn wider than the screen, never more than two screens,
 * and swiped sideways under it; it opens at the present, and the years under
 * it slide with it (R-0381). Whitlock's runs from 1924 to 1982. */
const line = (page: import("@playwright/test").Page) => page.locator("#view .ss-scroll");

const at = (page: import("@playwright/test").Page) =>
  line(page).evaluate((node) => ({
    left: node.scrollLeft,
    end: node.scrollWidth - node.clientWidth,
    screens: node.scrollWidth / node.clientWidth,
  }));

/** A swipe across the picture. */
const swipe = async (page: import("@playwright/test").Page, by: number) => {
  await line(page).hover();
  await page.mouse.wheel(-by, 0);
  await page.waitForTimeout(600);
};

const yearsUnder = (page: import("@playwright/test").Page) =>
  page.locator("#view .ep-yrs").allTextContents();

test.describe("the resting line on a long record", () => {
  test.use({ storageState: stateFor("whitlock") });

  // R-0381, R-0111, R-0543
  test("is wider than the screen, at most two screens, and opens at the present", async ({
    page,
  }) => {
    await settle(page);
    const stands = await at(page);
    expect(stands.end).toBeGreaterThan(0);
    expect(stands.screens).toBeLessThanOrEqual(2);
    expect(stands.left).toBe(stands.end);
    const years = await yearsUnder(page);
    expect(years[0]).toBe("1924");
    expect(years[years.length - 1]).toBe("1982");
  });

  // R-0381
  test("a swipe slides the line back toward its first year", async ({ page }) => {
    await settle(page);
    const { end } = await at(page);
    await swipe(page, 300);
    expect((await at(page)).left).toBeLessThan(end);
  });

  // R-0381
  test("going back to the whole timeline puts the line at the present", async ({ page }) => {
    await settle(page);
    await line(page).evaluate((s) => (s.scrollLeft = 0));
    await page.locator('.ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator('#path [data-step="0"]')).toBeVisible();
    await page.locator('#path [data-step="0"]').click();
    await page.waitForTimeout(400);
    const stands = await at(page);
    expect(stands.left).toBe(stands.end);
  });

  // R-0377, R-0543
  test("every dot and every pill sits on the wire", async ({ page }) => {
    await settle(page);
    const onWire = await page.locator("#view .ss svg").evaluate((svg) => {
      const wire = svg.querySelector("line.wire") as SVGLineElement;
      const y = Number(wire.getAttribute("y1"));
      const pills = [...svg.querySelectorAll("rect.pill")].map(
        (p) => Number(p.getAttribute("y")) + Number(p.getAttribute("height")) / 2,
      );
      const dots = [...svg.querySelectorAll("circle")].map((d) => Number(d.getAttribute("cy")));
      return pills.length > 0 && [...pills, ...dots].every((at) => at === y);
    });
    expect(onWire).toBe(true);
  });

  // R-0045, R-0381
  test("a tap still picks the cluster under the thumb after a swipe", async ({ page }) => {
    await settle(page);
    await swipe(page, 100);
    await page.locator('.ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator('#path [data-step="0"]')).toBeVisible();
  });
});

/** The line's width and where it starts, on every fixture record at phone and
 * desktop sizes, as the line before the pill strip drew them (8974698): two
 * screens starting at the present for the records whose clusters sit close,
 * one screen for the rest (R-0381). */
const BEFORE: Record<number, Partial<Record<Key, { width: number; start: number }>>> = {
  390: {
    one: { width: 390, start: 0 },
    three40: { width: 390, start: 0 },
    dense60: { width: 780, start: 390 },
    hostile: { width: 390, start: 0 },
    moves: { width: 390, start: 0 },
    play: { width: 390, start: 0 },
    longmove: { width: 390, start: 0 },
    longname: { width: 390, start: 0 },
    editable: { width: 390, start: 0 },
    whitlock: { width: 780, start: 390 },
  },
  1280: {
    one: { width: 538, start: 0 },
    three40: { width: 538, start: 0 },
    dense60: { width: 1076, start: 538 },
    hostile: { width: 538, start: 0 },
    moves: { width: 538, start: 0 },
    play: { width: 538, start: 0 },
    longmove: { width: 538, start: 0 },
    longname: { width: 538, start: 0 },
    editable: { width: 538, start: 0 },
    whitlock: { width: 1076, start: 538 },
  },
};

for (const key of Object.keys(BEFORE[390]) as Key[]) {
  test.describe(() => {
    test.use({ storageState: stateFor(key) });

    // R-0381
    test(`the ${key} line is as wide and starts where it did before the pill strip`, async ({
      page,
    }) => {
      await settle(page);
      const drawn = await line(page).evaluate((s) => ({
        width: s.scrollWidth,
        start: Math.round(s.scrollLeft),
      }));
      expect(drawn).toEqual(BEFORE[page.viewportSize()!.width][key]);
    });
  });
}

test.describe("what the picture never draws", () => {
  for (const key of ["one", "three40", "dense60", "moves"] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });

      // R-0284
      test(`no trend line joins the moments on the ${key} record`, async ({ page }) => {
        await settle(page);
        const sloped = await page.locator("#view svg").evaluateAll((svgs) =>
          svgs.flatMap((svg) => [
            ...[...svg.querySelectorAll("polyline, polygon, path")]
              .filter((n) => !n.closest("marker, defs"))
              .map((n) => n.outerHTML),
            ...[...svg.querySelectorAll("line")]
              .filter((n) => {
                const [x1, y1, x2, y2] = ["x1", "y1", "x2", "y2"].map((a) =>
                  Number(n.getAttribute(a)),
                );
                return x1 !== x2 && y1 !== y2;
              })
              .map((n) => n.outerHTML),
          ]),
        );
        expect(sloped).toEqual([]);
      });

      // R-0007
      test(`no progress bar on the ${key} record`, async ({ page }) => {
        await settle(page);
        await expect(page.locator('progress, meter, [role="progressbar"]')).toHaveCount(0);
      });

      // R-0007
      test(`nothing on the ${key} record says the family is finished`, async ({ page }) => {
        await settle(page);
        await expect(page.locator("#chat-screen .pic")).not.toContainText(
          /\d+ ?%|complete|finished|all done/i,
        );
      });
    });
  }
});

test.describe("a person with three directed points", () => {
  test.use({ storageState: stateFor("dense60") });

  // R-0284
  test("gets no step line: the only level lines are the wire and the seam", async ({
    page,
  }) => {
    await settle(page);
    const level = await page.locator("#view svg line").evaluateAll((lines) =>
      lines
        .filter((n) => n.getAttribute("y1") === n.getAttribute("y2"))
        .map((n) => n.getAttribute("class") ?? ""),
    );
    expect(level.length).toBeGreaterThan(0);
    expect(level.filter((c) => !/\b(wire|seam)\b/.test(c))).toEqual([]);
  });
});

test.describe("where the picture sits", () => {
  test.use({ storageState: stateFor("hostile") });

  // scrolled up, it folds to the strip in its place (Patrick, 2026-10-01, frame A1)
  // R-0002, R-0106
  test("above the chat, and it stays there while the chat scrolls", async ({ page }) => {
    await settle(page);
    const before = await boxOf(picture(page));
    const chat = await boxOf(page.locator("#chat"));
    expect(before.y + before.height).toBeLessThanOrEqual(chat.y + 1);
    await page.locator("#chat").evaluate((n) => (n.scrollTop = 0));
    await page.waitForTimeout(450);
    const after = await boxOf(picture(page));
    const moved = await boxOf(page.locator("#chat"));
    expect(after.y).toBe(before.y);
    expect(after.y + after.height).toBeLessThanOrEqual(moved.y + 1);
  });
});

test.describe("the coach's words drive the picture", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0001, R-0055, R-0543
  test("it opens on what the coach's last message named", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#view .ss-name")).toHaveText("The walk (17)");
    await expect(page.locator('#path [data-step="0"]')).toBeVisible();
    // the two events it named are inside one cluster, so its pill is lit
    await expect(page.locator("#view rect.pill.on")).toHaveCount(1);
  });
});

test.describe("an event added by hand", () => {
  test.use({ storageState: stateFor("editable") });

  // R-0055
  test("is on the picture as soon as it is saved", async ({ page }, info) => {
    await settle(page);
    const before = await page.locator("#view circle.dot").count();
    await openList(page);
    await addForm(page, "event");
    const editor = page.locator("#add-sheet .editor");
    // a move is a noted event; a new event opens as a shift, which is refused
    // until something in it moves
    await editor.locator('.segs[data-name="kind"] .seg[data-value="noted"]').click();
    // a noted event is about someone: the record refuses one about nobody (R-0593)
    await editor.locator('.segs[data-name="person"] .seg:not([data-value=""])').first().click();
    // each project adds its own, a month apart: the record keeps what an
    // earlier project added, and refuses a second noted event on the same day
    const words = `Moved back (${info.project.name})`;
    const month = 1 + info.config.projects.findIndex((p) => p.name === info.project.name);
    await editor.locator('.f[data-name="title"]').fill(words);
    await editor.locator('.f[data-name="description"]').fill("Moved back in with her parents");
    await editor.locator('.f[data-name="dateTime"]').fill(`2024-${String(month).padStart(2, "0")}-01`);
    await editor.locator(".save").click();
    await expect(page.locator("#menu-body")).toContainText(words);
    if (!(await pinned(page))) await page.locator("#menu-close").click();
    await expect(page.locator("#view circle.dot")).toHaveCount(before + 1);
  });
});

test.describe("a tap on the picture reaches the coach", () => {
  test.use({ storageState: stateFor("three40") });

  const sent = (page: import("@playwright/test").Page) =>
    page.waitForRequest(
      (r) => r.url().endsWith("/app/interactions") && r.method() === "POST",
      { timeout: 5000 },
    );

  // R-0065, R-0543
  test("a tap on a dot is sent, naming the event touched", async ({ page }) => {
    await settle(page);
    const posted = sent(page);
    // the one event no cluster claims is the one with a dot
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    expect((await posted).postDataJSON()).toMatchObject({ item_kind: "event", item_id: "13" });
  });

  // R-0065
  test("a tap that opens a cluster is sent, naming the cluster", async ({ page }) => {
    await settle(page);
    const posted = sent(page);
    await page.locator('.ss-hit[data-target="cluster"]').first().click();
    expect((await posted).postDataJSON()).toMatchObject({ item_kind: "cluster", item_id: "cT" });
  });
});

/** Border colour and corner of a control, which is what tells a reader what
 * a tap on it will do. */
const outline = (loc: import("@playwright/test").Locator) =>
  loc.evaluate((n) => {
    const s = getComputedStyle(n);
    return [s.borderTopColor, s.borderTopLeftRadius];
  });

test.describe("the mark that says a tap goes into the message", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0068
  test("the ask in the row and the coach's offers wear the same outline", async ({
    page,
  }) => {
    test.fixme(true, "the ask chip is hidden for now (Patrick, 2026-09-29)");
    await settle(page);
    // the record opens on a cluster, and the row offers ask for it
    await expect(page.locator("#cap-chip")).toBeVisible();
    const ask = await outline(page.locator("#cap-chip"));
    expect(await outline(page.locator(".bub .chip.ask").first())).toEqual(ask);
    // a reference aims the picture and sends nothing, so it looks different
    const reference = await outline(page.locator(".bub .chip.data").first());
    expect(reference[0]).not.toBe(ask[0]);
  });

  // R-0068
  test("an offer goes into the message and a reference does not", async ({ page }) => {
    await settle(page);
    await page.locator(".bub .chip.ask").first().click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
    await page.locator(".bub .chip.data").first().click();
    await expect(page.locator("#composer .chip")).toHaveCount(1);
  });
});

test.describe("the colours come from named tokens", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0023
  test("renaming the reference colour repaints every reference chip", async ({ page }) => {
    await settle(page);
    await page.evaluate(() =>
      document.documentElement.style.setProperty("--data", "rgb(1, 2, 3)"),
    );
    const colours = await page
      .locator(".bub .chip.data")
      .evaluateAll((chips) => chips.map((c) => getComputedStyle(c).color));
    expect(colours.length).toBeGreaterThan(0);
    expect(new Set(colours)).toEqual(new Set(["rgb(1, 2, 3)"]));
  });

  // R-0023
  test("a second scheme repaints the page with no code of its own", async ({ page }) => {
    await settle(page);
    const paint = () =>
      page.evaluate(() => [
        getComputedStyle(document.body).backgroundColor,
        getComputedStyle(document.querySelector(".bub .chip.data")!).color,
      ]);
    const light = await paint();
    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "dark"));
    const dark = await paint();
    expect(dark[0]).not.toBe(light[0]);
    expect(dark[1]).not.toBe(light[1]);
  });
});

test.describe("an untouched session", () => {
  test.use({ storageState: stateFor("empty") });

  // R-0139
  test("asks for the first message in the chat, not on the picture", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#chat .cta")).toContainText("Tell your coach who is on your mind");
    await expect(picture(page)).not.toContainText("Tell your coach");
  });

  // R-0351
  test("the picture is one sentence in its middle", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#view")).toHaveText("The timeline draws itself here as you talk.");
    const off = await page.locator("#view .ss-empty").evaluate((p) => {
      const range = document.createRange();
      range.selectNodeContents(p);
      const words = range.getBoundingClientRect();
      const view = document.querySelector("#view")!.getBoundingClientRect();
      return [
        Math.abs(words.x + words.width / 2 - (view.x + view.width / 2)),
        Math.abs(words.y + words.height / 2 - (view.y + view.height / 2)),
      ];
    });
    expect(off[0]).toBeLessThanOrEqual(2);
    expect(off[1]).toBeLessThanOrEqual(2);
  });

  // R-0351
  test("the row under it carries no hint", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#caption")).toHaveText("");
  });
});

test.describe("the picture while the reader looks around", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0139
  test("never says it is about to change", async ({ page }) => {
    await settle(page);
    const quiet = /\b(will|about to|soon|loading|updating|coming up)\b/i;
    await expect(picture(page)).not.toContainText(quiet);
    await openCluster(page);
    await expect(picture(page)).not.toContainText(quiet);
    await page.locator('.ss-hit[data-target="zone"]').first().click();
    await expect(picture(page)).not.toContainText(quiet);
  });
});

test.describe("a record with undated facts beside dated ones", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0359
  test("draws no question mark past the end of the line", async ({ page }) => {
    await page.route("**/app/timeline*", async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      json.shelf = [{ event_id: 99, label: "the house", sentence: "Something with the house." }];
      await route.fulfill({ response, json });
    });
    await settle(page);
    await expect(page.locator('#view [data-target="shelf"]')).toHaveCount(0);
    await expect(page.locator("#view .qm")).toHaveCount(0);
    await openCluster(page);
    await expect(page.locator('#view [data-target="shelf"]')).toHaveCount(0);
    await expect(page.locator("#view .qm")).toHaveCount(0);
  });
});

test.describe("a moment named in the coach's words", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0282
  test("is an outlined pill with nothing filled in", async ({ page }) => {
    await settle(page);
    const chip = await page.locator(".bub.coach .chip.data").first().evaluate((n) => {
      const s = getComputedStyle(n);
      return {
        edge: `${s.borderTopWidth} ${s.borderTopStyle}`,
        fill: s.backgroundColor,
        round: parseFloat(s.borderTopLeftRadius),
      };
    });
    expect(chip.edge).toBe("1px solid");
    expect(chip.fill).toBe("rgba(0, 0, 0, 0)");
    expect(chip.round).toBeGreaterThanOrEqual(8);
  });
});

test.describe("a moment's mark", () => {
  /** Circles drawn on the centre of another circle: a ring or band around a mark. */
  const ringed = (page: import("@playwright/test").Page) =>
    page.locator("#view svg").evaluateAll((svgs) =>
      svgs.flatMap((svg) => {
        const circles = [...svg.querySelectorAll("circle")].map((c) => ({
          x: c.getAttribute("cx"),
          y: c.getAttribute("cy"),
          html: c.outerHTML,
        }));
        return circles
          .filter((c, i) => circles.some((o, j) => j !== i && o.x === c.x && o.y === c.y))
          .map((c) => c.html);
      }),
    );

  for (const key of ["one", "three40", "dense60"] as const) {
    test.describe(() => {
      test.use({ storageState: stateFor(key) });

      // R-0467
      test(`has nothing drawn around it, at rest or in an open cluster, on the ${key} record`, async ({
        page,
      }) => {
        await settle(page);
        expect(await ringed(page)).toEqual([]);
        const cluster = page.locator('.ss-hit[data-target="cluster"]').first();
        if (await cluster.count()) {
          await cluster.click();
          await page.waitForTimeout(500);
          await expect(page.locator('#path [data-step="0"]')).toBeVisible();
          expect(await ringed(page)).toEqual([]);
        }
      });
    });
  }
});

/** Any control a reader could take for renaming, deleting or regrouping a
 * cluster, in the picture region and its title row. An event's dot is named by
 * the event's own words ("The move across the country"), which say nothing
 * about the cluster, so the dots are left out. */
const clusterEdits = (page: import("@playwright/test").Page) =>
  page
    .locator(".titlerow, #chat-screen .pic")
    .locator(
      `button:not([data-target="zone"]), [role=button], input, textarea, [contenteditable=true]`,
    )
    .evaluateAll((controls) =>
      controls
        .filter((c) => !(c as HTMLElement).hidden && (c as HTMLElement).offsetParent !== null)
        .map((c) => `${c.textContent ?? ""} ${c.getAttribute("aria-label") ?? ""}`)
        .filter((words) => /rename|delete|remove|regroup|merge|split|edit|move/i.test(words)),
    );

test.describe("a cluster the reader has open", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0282
  test("offers no way to rename, delete or regroup it, nor does its i page", async ({
    page,
  }) => {
    await settle(page);
    await openCluster(page);
    expect(await clusterEdits(page)).toEqual([]);
    await page.locator("#info").click();
    await expect(page.locator("#view")).toContainText("Ada lost her grandmother");
    expect(await clusterEdits(page)).toEqual([]);
  });
});

