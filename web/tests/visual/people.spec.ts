import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The list behind the picture, and the button that opens it.
 *
 * The button sits inside the picture, at the end of the row of chips and drawn
 * their height: the list button belongs to the thing it lists. The list itself
 * is two ways into one record — what happened, and who it happened to. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

const openList = async (page: Page) => {
  await page.locator("#menu-open").click();
  await expect(page.locator("#menu-screen")).toBeVisible();
};

const personEditor = async (page: Page) => {
  await settle(page);
  await openList(page);
  await page.locator("#tab-people").click();
  await page.locator("#menu-body .row").first().click();
  await expect(page.locator("#menu-body .editor")).toBeVisible();
};

test.describe("the button that opens the list", () => {
  test.use({ storageState: stateFor("three40") });

  // R-0221, R-0234, R-0198
  test("sits at the end of the row of chips, drawn their height on their line", async ({
    page,
  }) => {
    await settle(page);
    await page.locator('#view .ss-hit[data-target="cluster"]').first().click();
    await expect(page.locator("#cap-chip")).toBeVisible();
    const where = await page.evaluate(() => {
      const button = document.getElementById("menu-open")!;
      const row = document.querySelector(".caption")!;
      const chip = document.getElementById("cap-chip")!;
      const box = button.getBoundingClientRect();
      const drawn = getComputedStyle(button, "::before");
      const beside = chip.getBoundingClientRect();
      return {
        inRow: row.contains(button),
        inTitleRow: !!document.querySelector(".titlerow #menu-open"),
        inNameRow: !!document.querySelector(".pin-label #menu-open"),
        size: [Math.round(box.width), Math.round(box.height)],
        last: row.lastElementChild === button,
        height: [parseFloat(drawn.height), beside.height],
        corner: [drawn.borderRadius, getComputedStyle(chip).borderRadius],
        line: [box.top + box.height / 2, beside.top + beside.height / 2].map(Math.round),
      };
    });
    expect(where.inRow).toBe(true);
    expect(where.inTitleRow).toBe(false);
    expect(where.inNameRow).toBe(false);
    expect(where.last).toBe(true);
    expect(where.size).toEqual([44, 44]);
    expect(where.height[0]).toBe(where.height[1]);
    expect(where.corner[0]).toBe(where.corner[1]);
    expect(where.line[0]).toBe(where.line[1]);
  });
});

test.describe("the list button's place", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0198
  test("lies inside the picture's own frame, not in the message bar", async ({ page }) => {
    await settle(page);
    const where = await page.evaluate(() => {
      const button = document.getElementById("menu-open")!;
      const pic = document.querySelector("#chat-screen .pic")!;
      const a = button.getBoundingClientRect();
      const b = pic.getBoundingClientRect();
      return {
        inPicture: pic.contains(button),
        inBar: !!button.closest(".inbar"),
        within: a.left >= b.left - 1 && a.right <= b.right + 1 && a.top >= b.top - 1 && a.bottom <= b.bottom + 1,
      };
    });
    expect(where).toEqual({ inPicture: true, inBar: false, within: true });
  });

  // R-0198
  test("carries the same three-line mark as the sessions button", async ({ page }) => {
    await settle(page);
    const mark = (selector: string) =>
      page.locator(selector).evaluate((b) => {
        const svg = b.querySelector("svg")!;
        return {
          path: svg.querySelector("path")!.getAttribute("d"),
          size: `${svg.getAttribute("width")}x${svg.getAttribute("height")}`,
          opacity: getComputedStyle(svg).opacity,
          text: (b.textContent ?? "").trim(),
        };
      });
    const list = await mark("#menu-open");
    expect(list).toEqual(await mark("#sessions-open"));
    expect(list.text).toBe("");
  });
});

test.describe("the two lists behind it", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0345, R-0199
  test("open on events, and people are a tap away", async ({ page }) => {
    await settle(page);
    await openList(page);
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(page.locator("#menu-body .row").first()).toBeVisible();

    await page.locator("#tab-people").click();
    await expect(page.locator("#tab-people")).toHaveClass(/on/);
    await expect(page.locator("#menu-add")).toHaveText("+ Add someone");
    // the moves record holds three people
    await expect(page.locator("#menu-body .row")).toHaveCount(3);
    await expect(page.locator("#menu-body .row").first()).toContainText("Ada");
  });

  // R-0345
  test("a person opens the editor on the fields the record keeps", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await page.locator("#menu-body .row").first().click();

    const editor = page.locator("#menu-body .editor");
    await expect(editor).toBeVisible();
    await expect(editor.locator('[data-name="name"]')).toHaveValue("Ada");
    await expect(editor.locator('.segs[data-name="gender"] .seg')).toHaveCount(5);
    await expect(editor.locator(".save")).toBeVisible();
    await expect(editor.locator(".del")).toBeVisible();
  });

  // R-0141
  test("a name typed in the editor is on the record after saving", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await page.locator("#menu-body .row").first().click();
    await page.locator("#menu-body .editor [data-name=\"last_name\"]").fill("Ellis");
    await page.locator("#menu-body .editor .save").click();
    await expect(page.locator("#menu-body .editor")).toHaveCount(0);
    await expect(page.locator("#menu-body .row").first()).toContainText("Ellis");
  });

  // R-0199
  test("the two lists are tabs of one drawer, one selected at a time", async ({ page }) => {
    await settle(page);
    await openList(page);
    const tabs = page.locator("#menu-tabs [role=tab]");
    await expect(tabs).toHaveText(["Events", "People", "From the coach"]);
    await expect(page.locator('#menu-tabs [aria-selected="true"]')).toHaveText("Events");
    await expect(page.locator("#menu-body [data-event]").first()).toBeVisible();
    const drawer = await page.locator("#menu-screen").elementHandle();

    await page.locator("#tab-people").click();
    await expect(page.locator('#menu-tabs [aria-selected="true"]')).toHaveText("People");
    await expect(page.locator('#menu-tabs [aria-selected="true"]')).toHaveCount(1);
    // the other list takes the drawer's place whole, rather than narrowing it
    await expect(page.locator("#menu-body [data-event]")).toHaveCount(0);
    await expect(page.locator("#menu-body [data-person]")).toHaveCount(3);
    expect(await page.locator("#menu-screen").evaluate((n, d) => n === d, drawer)).toBe(true);
    await expect(page.locator("#menu-screen")).toBeVisible();
  });

  // R-0218
  test("the events list's cluster headings keep their words clear of the scroll bar", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await expect(page.locator("#menu-body .div").first()).toBeVisible();
    const crowded = await page.evaluate(() => {
      const list = document.getElementById("menu-body")!;
      const edge = list.getBoundingClientRect().right;
      // the width an overlay scroll bar is drawn over at the list's right edge
      const bar = 12;
      return [...list.querySelectorAll(".div")].flatMap((head) =>
        [...head.children]
          .filter((words) => words.getBoundingClientRect().right > edge - bar)
          .map((words) => words.textContent),
      );
    });
    expect(crowded).toEqual([]);
  });

  // R-0218
  test("the lists hold a gutter for a scroll bar that takes room", async ({ page }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await expect(page.locator("#menu-body .div").first()).toBeVisible();
    const look = await page.evaluate(() => {
      const list = document.getElementById("menu-body")!;
      const head = list.querySelector(".div")!;
      const edge = list.getBoundingClientRect().right;
      return {
        gutter: getComputedStyle(list).scrollbarGutter,
        clear: [...head.children].every((w) => w.getBoundingClientRect().right <= edge - 12),
      };
    });
    expect(look.gutter).toBe("stable");
    expect(look.clear).toBe(true);
  });

  // R-0174
  test("every one-line field in the person editor is 44px with room inside it", async ({
    page,
  }) => {
    await personEditor(page);
    const fields = await page
      .locator("#menu-body .editor input.f")
      .evaluateAll((all) =>
        all
          .filter((n) => (n as HTMLElement).offsetParent)
          .map((n) => {
            const style = getComputedStyle(n);
            return {
              height: Math.round(n.getBoundingClientRect().height),
              left: style.paddingLeft,
              right: style.paddingRight,
            };
          }),
      );
    expect(fields.length).toBeGreaterThan(0);
    for (const field of fields) {
      expect(field.height).toBe(44);
      expect(parseFloat(field.left)).toBeGreaterThanOrEqual(12);
      expect(field.right).toBe(field.left);
    }
  });

  // R-0459
  test("the people list orders by birth until the reader asks for names", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await expect(page.locator("#menu-body .div")).toContainText("by birth");
    await page.locator("#menu-body [data-order]").click();
    await expect(page.locator("#menu-body .div")).toContainText("by name");
  });
});

test.describe("the list views and their editors", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0219
  test("the events list does not say it can also be edited by chatting", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await expect(page.locator("#menu-body .row").first()).toBeVisible();
    await expect(page.locator("#menu-screen")).not.toContainText(/chat/i);
  });

  // R-0219
  test("the people list does not say it can also be edited by chatting", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#tab-people").click();
    await expect(page.locator("#menu-body .row").first()).toContainText("Ada");
    await expect(page.locator("#menu-screen")).not.toContainText(/chat/i);
  });

  // R-0200
  test("a person's symbol field is labelled Kind", async ({ page }) => {
    await personEditor(page);
    const labels = await page.locator("#menu-body .editor .lab").allTextContents();
    expect(labels).toContain("Kind");
  });

  // R-0200
  test("no label in the person editor says sex or gender", async ({ page }) => {
    await personEditor(page);
    const labels = await page.locator("#menu-body .editor .lab").allTextContents();
    expect(labels.length).toBeGreaterThan(0);
    expect(labels.filter((l) => /sex|gender/i.test(l))).toEqual([]);
  });

  // R-0145
  test("a shift's four changes sit together under one Shifts heading", async ({
    page,
  }) => {
    await settle(page);
    await openList(page);
    await page.locator("#menu-body .row").first().click();
    const block = page.locator('#menu-body .editor [data-block="shift"]');
    await expect(block).toBeVisible();
    await expect(block.locator(".sec")).toHaveText(["Shifts"]);
    const labels = await block.locator(":scope > .lab").allTextContents();
    expect(labels).toEqual([
      "Δ symptom",
      "Δ anxiety",
      "Δ functioning",
      "Δ relationship",
    ]);
  });
});

test.describe("the picture", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0203
  test("never says it is behind the conversation", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#fresh")).toHaveCount(0);
    await expect(page.locator(".fresh")).toHaveCount(0);
  });
});

/** Where the lists stand on a window of this size, for a fixture with no
 * professional licence. */
const listBesideChat = async (page: Page) => {
  await settle(page);
  expect(await page.evaluate(() => window.BOOTSTRAP.user?.pro)).not.toBe(true);
  const drawer = page.locator("#chat-drawer");
  await expect(drawer).toBeVisible();
  await expect(drawer.locator("#menu-body .row").first()).toBeVisible();
  await expect(page.locator("#menu-open")).toBeHidden();
  return page.evaluate(() => {
    const chat = document.getElementById("chat-screen")!.getBoundingClientRect();
    const list = document.getElementById("chat-drawer")!.getBoundingClientRect();
    return list.left >= chat.right - 1 || list.right <= chat.left + 1;
  });
};

test.describe("a phone on its side", () => {
  test.use({ storageState: stateFor("moves"), viewport: { width: 844, height: 390 } });

  // R-0367
  test("stands the lists beside the chat without a professional licence", async ({
    page,
  }) => {
    expect(await listBesideChat(page)).toBe(true);
  });
});

test.describe("a desktop window", () => {
  test.use({ storageState: stateFor("moves"), viewport: { width: 1280, height: 800 } });

  // R-0367, R-0352
  test("stands the lists beside the chat without a professional licence", async ({
    page,
  }) => {
    expect(await listBesideChat(page)).toBe(true);
  });

  // R-0352
  test("draws no list button in the picture's row of chips", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#chat-drawer")).toBeVisible();
    await expect(page.locator("#caption")).toBeVisible();
    await expect(page.locator("#caption > *").first()).toBeVisible();
    await expect(page.locator("#caption .listglyph:visible, #menu-open:visible")).toHaveCount(0);
  });
});

test.describe("the two views of the record", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0109
  test("one picture above the chat, and the timeline list a tap away", async ({ page }) => {
    await settle(page);
    await expect(page.locator("#chat-screen .pic #view > .ss")).toHaveCount(1);
    await openList(page);
    await expect(page.locator("#tab-events")).toHaveClass(/on/);
    await expect(page.locator("#menu-body .row").first()).toBeVisible();
  });
});
