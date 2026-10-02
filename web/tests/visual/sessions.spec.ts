import { expect, test, type Page } from "@playwright/test";
import { colours } from "./gate";
import { flask, stateFor, username, boxOf } from "./setup";

/** The sheet's door beside the message box, and the sheet it raises. Only a
 * professional or Patrick has one, and no fixture is either of them, so the
 * door is shown here the way their bootstrap shows it. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.locator("#sessions-open").evaluate((b) => ((b as HTMLElement).hidden = false));
  await page.waitForTimeout(600);
};

/** Which of the sheets and scrims are on the page, and whether the chat under
 * them is still shrunk back. */
const shown = async (page: Page) => {
  await page.waitForTimeout(400);
  return page.evaluate(() => ({
    up: ["sessions-sheet", "sessions-scrim", "recording-sheet", "recording-scrim"].filter(
      (id) => !(document.getElementById(id) as HTMLElement).hidden,
    ),
    chat: (document.querySelector("#chat-screen") as HTMLElement).style.transform,
  }));
};

/** The app's close button in the sheet: teal, in the sheet's top-right corner
 * beside the search field, and a tap on it leaves the page as a tap on the
 * scrim does. */
const closes = async (page: Page, sheet: string, scrim: string, open: () => Promise<void>) => {
  await open();
  await page.locator(scrim).click({ position: { x: 195, y: 20 } });
  const byScrim = await shown(page);
  await open();
  const x = page.locator(`${sheet} > .cardx`);
  await expect(x).toHaveCount(1);
  await expect(x).toHaveText("\u00d7");
  const { light, dark } = await colours(page, x);
  expect(light.drawn).toBe(light.token);
  expect(dark.drawn).toBe(dark.token);
  const [b, p] = [await boxOf(x), await boxOf(page.locator(sheet))];
  expect(p.x + p.width - (b.x + b.width)).toBeLessThanOrEqual(8);
  // beside the search field, on a sheet that has one
  const f = await page.locator(`${sheet} .fs-search input`).boundingBox();
  if (f) {
    expect(Math.abs(b.y + b.height / 2 - (f.y + f.height / 2))).toBeLessThanOrEqual(4);
    expect(f.x + f.width).toBeLessThanOrEqual(b.x);
  }
  await x.click();
  expect(await shown(page)).toEqual(byScrim);
};

const openSheet = async (page: Page) => {
  await page.locator("#sessions-open").click();
  await expect(page.locator("#sessions-sheet")).toBeVisible();
  await page.waitForTimeout(400);
};

test.describe("the sessions sheet", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0234, R-0090
  test("the button sits in the input bar, not the title row", async ({ page }) => {
    await settle(page);
    const button = page.locator("#sessions-open");
    await expect(button).toBeVisible();
    const inBar = await button.evaluate((node) => !!node.closest(".inbar"));
    expect(inBar).toBe(true);
    const box = await boxOf(button);
    expect(Math.round(box.width)).toBe(44);
    expect(Math.round(box.height)).toBe(44);
  });

  // R-0090
  test("the button stands right beside the message box, and the title row has none", async ({
    page,
  }) => {
    await settle(page);
    await expect(page.locator(".titlerow #sessions-open, .titlerow [aria-label='sessions']")).toHaveCount(0);
    const button = await boxOf(page.locator("#sessions-open"));
    const field = await boxOf(page.locator("#composer"));
    const middle = (b: { y: number; height: number }) => b.y + b.height / 2;
    expect(Math.abs(middle(button) - middle(field))).toBeLessThanOrEqual(2);
    const gap = field.x - (button.x + button.width);
    expect(gap).toBeGreaterThanOrEqual(0);
    expect(gap).toBeLessThanOrEqual(16);
  });

  // R-0092
  test("the button is a hairline circle with a fill and three lines at 80%", async ({
    page,
  }) => {
    // the circle's size is R-0234's, which superseded the 34px here
    await settle(page);
    const look = await page.locator("#sessions-open").evaluate((b) => {
      const ring = getComputedStyle(b, "::before");
      const svg = b.querySelector("svg")!;
      return {
        round: ring.borderRadius,
        border: ring.borderTopWidth,
        fill: ring.backgroundColor,
        lines: svg.querySelector("path")!.getAttribute("d")!.split("M").length - 1,
        opacity: getComputedStyle(svg).opacity,
      };
    });
    expect(look.round).toBe("50%");
    expect(look.border).toBe("1px");
    expect(look.fill).not.toBe("rgba(0, 0, 0, 0)");
    expect(look.lines).toBe(3);
    expect(look.opacity).toBe("0.8");
  });

  // R-0092
  test("the button is never a bare text character", async ({ page }) => {
    await settle(page);
    const button = page.locator("#sessions-open");
    expect(await button.evaluate((b) => b.textContent!.trim())).toBe("");
    await expect(button.locator("svg")).toBeVisible();
  });

  // R-0095
  test("it opens to 92% of the frame with a grabber", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    const frame = await boxOf(page.locator(".app"));
    const sheet = await boxOf(page.locator("#sessions-sheet"));
    expect(Math.round(sheet.height)).toBe(Math.round(frame.height * 0.92));
    // the page holds several sheets of this class; only this one is the sessions'
    await expect(page.locator("#sessions-sheet .fs-grab")).toBeVisible();
  });

  // R-0055
  test("it lists no conversation to open and offers none to start", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await expect(page.locator("#sessions-sheet .fs-search")).toBeHidden();
    await expect(page.locator("#sessions-sheet .row")).toHaveCount(0);
    expect(await page.locator("#sessions-sheet").innerText()).not.toMatch(/new session/i);
  });

  // R-0095
  test("tapping the scrim closes it", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator("#sessions-scrim").click({ position: { x: 195, y: 20 } });
    await page.waitForTimeout(400);
    await expect(page.locator("#sessions-sheet")).toBeHidden();
  });

  // R-0588, R-0589
  test("the app's close button sits in its top-right corner and closes it as a tap on the scrim does", async ({ page }) => {
    await settle(page);
    await closes(page, "#sessions-sheet", "#sessions-scrim", () => openSheet(page));
  });

  // R-0103
  test("every row and control in the sheet meets the 44px floor", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const small = await page.evaluate(() =>
      [
        ...document.querySelectorAll(
          ".fs-sheet button, .fs-sheet input, .fs-body .row",
        ),
      ]
        .map((node) => ({
          what: node.className || node.tagName,
          height: Math.round(node.getBoundingClientRect().height),
        }))
        .filter((row) => row.height > 0 && row.height < 44),
    );
    expect(small).toEqual([]);
  });

  /** A reader without the professional licence never meets the word case, and
   * the plus beside a family starts a session on that family [R-0285]. */
  // R-0285
  test("the sheet never says case, and each family carries its own plus", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const sheet = page.locator("#sessions-sheet");
    expect(await sheet.innerText()).not.toMatch(/\bcases?\b/i);
    // the family is chosen on the account page, never here (R-0347)
    await expect(page.locator(".fs-fhead")).toHaveCount(0);
  });
});

test.describe("uploading a recording", () => {
  test.use({ storageState: stateFor("moves") });

  /** Tap the upload button; whether a file picker opened. */
  const upload = async (page: Page) => {
    await settle(page);
    await openSheet(page);
    // the button shows only for a professional licence, which no fixture holds
    const button = page.locator("#sessions-sheet .fs-upload");
    await button.evaluate((b) => ((b as HTMLElement).hidden = false));
    let picked = false;
    page.on("filechooser", () => (picked = true));
    await button.click();
    await expect(page.locator(".cf-p").first()).toBeVisible();
    await page.waitForTimeout(300);
    return picked;
  };

  // R-0588, R-0589
  test("the warning has the app's close button in its top-right corner, which closes it as a tap on the scrim does", async ({ page }) => {
    await settle(page);
    await closes(page, "#recording-sheet", "#recording-scrim", async () => {
      await openSheet(page);
      const button = page.locator("#sessions-sheet .fs-upload");
      await button.evaluate((b) => ((b as HTMLElement).hidden = false));
      await button.click();
      await expect(page.locator("#recording-sheet")).toBeVisible();
      await page.waitForTimeout(400);
    });
  });

  // R-0349
  test("warns before the file picker opens", async ({ page }) => {
    expect(await upload(page)).toBe(false);
  });

  // R-0349
  test("the warning says it costs Alaska Family Systems money and who to ask", async ({
    page,
  }) => {
    await upload(page);
    const warning = page.locator(".cf-p");
    await expect(warning.first()).toContainText("costs Alaska Family Systems money");
    await expect(warning.last()).toContainText("patrick@alaskafamilysystems.com");
  });
});

/** Only Patrick sees a family's sessions listed, twelve of them on this
 * fixture. His search reads what was said in each session, not only its title
 * and summary: a word said only inside one session finds that session, with
 * the line that carries it under its title. */
test.describe("the sessions Patrick sees listed", () => {
  test.use({ storageState: stateFor("sittings") });
  const roles = (...names: string[]) =>
    flask("admin", "run", "--", "users", "roles", username("sittings"), ...names, "--yes");
  test.beforeAll(() => roles("admin", "subscriber"));
  test.afterAll(() => roles("subscriber"));

  const rows = async (page: Page) => {
    await page.goto("/app/");
    await openSheet(page);
    await expect(page.locator("#sessions-sheet .fs-body .row")).toHaveCount(12);
    return page.locator("#sessions-sheet .fs-body .row").evaluateAll((all) =>
      all.map((r) => {
        const box = r.getBoundingClientRect();
        const style = getComputedStyle(r);
        const behind = [getComputedStyle(r, "::before"), getComputedStyle(r, "::after")];
        return {
          top: box.top,
          bottom: box.bottom,
          left: Math.round(box.left),
          width: Math.round(box.width),
          transform: style.transform,
          cards: behind.filter((b) => b.content !== "none" && b.boxShadow !== "none").length,
        };
      }),
    );
  };

  // R-0096
  test("are a plain list: one column, none laid over another", async ({ page }) => {
    const all = await rows(page);
    expect(new Set(all.map((r) => `${r.left} ${r.width}`)).size).toBe(1);
    all.slice(1).forEach((r, i) => expect(r.top).toBeGreaterThanOrEqual(all[i].bottom - 1));
  });

  // R-0096
  test("are not dressed as stacked cards: no offset, tilt or card behind", async ({ page }) => {
    const all = await rows(page);
    expect(all.filter((r) => r.transform !== "none" || r.cards)).toEqual([]);
  });

  // R-0259, R-0267
  test("holds no way to coding, the meeting or the replies, and a row goes to its session, renames or deletes", async ({
    page,
  }) => {
    await page.goto("/app/");
    await openSheet(page);
    await expect(page.locator("#sessions-sheet .fs-foot button:visible")).toHaveCount(0);
    const row = page.locator("#sessions-sheet .row").first();
    await row.locator(".rsub").click();
    await expect(page.locator("#cut-strip")).toBeHidden();
    await expect(page.locator("#sessions-sheet")).toBeHidden();
    await openSheet(page);
    await row.locator(".rmore").click();
    await expect(page.locator("#sessions-sheet .fs-act")).toHaveText(["Rename", "Delete"]);
  });

  // R-0347
  test("finds a session by a word said only inside it", async ({ page }) => {
    await page.goto("/app/");
    await openSheet(page);
    await page.locator("#sessions-sheet .fs-search input").fill("job");
    const rows = page.locator("#sessions-sheet .row");
    await expect(rows).toHaveCount(1);
    await expect(rows.locator(".rtitle")).not.toContainText("job");
    await expect(rows.locator(".rsub")).toHaveText("What happened first, with my brother's job?");
  });
});
