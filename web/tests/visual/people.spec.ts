import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The list behind the picture, and the button that opens it.
 *
 * The button sits inside the picture, in the same circle as the one beside the
 * message bar: the list button belongs to the thing it lists. The list itself
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
  test.use({ storageState: stateFor("moves") });

  // R-0221, R-0234
  test("sits at the end of the row of chips, dressed like the sessions button", async ({
    page,
  }) => {
    await settle(page);
    const where = await page.evaluate(() => {
      const button = document.getElementById("menu-open")!;
      const row = document.querySelector(".caption")!;
      const sessions = document.getElementById("sessions-open")!;
      const box = button.getBoundingClientRect();
      const round = (n: HTMLElement) => {
        const mark = getComputedStyle(n, "::before");
        return `${mark.width} ${mark.height} ${mark.borderRadius} ${mark.borderTopWidth}`;
      };
      return {
        inRow: row.contains(button),
        inTitleRow: !!document.querySelector(".titlerow #menu-open"),
        inNameRow: !!document.querySelector(".pin-label #menu-open"),
        size: [Math.round(box.width), Math.round(box.height)],
        last: row.lastElementChild === button,
        same: round(button) === round(sessions),
      };
    });
    expect(where.inRow).toBe(true);
    expect(where.inTitleRow).toBe(false);
    expect(where.inNameRow).toBe(false);
    expect(where.last).toBe(true);
    expect(where.size).toEqual([44, 44]);
    expect(where.same).toBe(true);
  });
});

test.describe("the two lists behind it", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0345
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

  // no ruling
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

  // R-0367
  test("stands the lists beside the chat without a professional licence", async ({
    page,
  }) => {
    expect(await listBesideChat(page)).toBe(true);
  });
});
