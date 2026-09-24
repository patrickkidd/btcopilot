import { expect, test, type Page } from "@playwright/test";
import { EXACT, stateFor } from "./setup";

/** The session door: the button beside the message box and the family-sections
 * sheet it raises. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
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
    const box = (await button.boundingBox())!;
    expect(Math.round(box.width)).toBe(44);
    expect(Math.round(box.height)).toBe(44);
  });

  // R-0090
  test("the button stands right beside the message box, and the title row has none", async ({
    page,
  }) => {
    await settle(page);
    await expect(page.locator(".titlerow #sessions-open, .titlerow [aria-label='sessions']")).toHaveCount(0);
    const button = (await page.locator("#sessions-open").boundingBox())!;
    const field = (await page.locator("#composer").boundingBox())!;
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

  // R-0347, R-0095
  test("it opens to 92% of the frame with a grabber and a search field", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    const frame = (await page.locator(".app").boundingBox())!;
    const sheet = (await page.locator("#sessions-sheet").boundingBox())!;
    expect(Math.round(sheet.height)).toBe(Math.round(frame.height * 0.92));
    // the page holds several sheets of this class; only this one is the sessions'
    await expect(page.locator("#sessions-sheet .fs-grab")).toBeVisible();
    // R-0347: the sheet lists only this family's sessions, so it searches sessions
    await expect(page.locator("#sessions-sheet .fs-search input")).toHaveAttribute(
      "placeholder",
      "Search sessions",
    );
    const field = (await page.locator("#sessions-sheet .fs-search input").boundingBox())!;
    expect(Math.round(field.height)).toBe(44);
  });

  // R-0347
  test("it lists the sessions under a day heading, and marks the current one", async ({
    page,
  }) => {
    await settle(page);
    await openSheet(page);
    await expect(page.locator("#sessions-sheet .fs-body .ghead").first()).not.toBeEmpty();
    await expect(page.locator("#sessions-sheet .fs-body .row").first()).toBeVisible();
    await expect(page.locator("#sessions-sheet .fs-body .row.cur")).toHaveCount(1);
    // the foot also carries the upload and note buttons of the same class
    await expect(page.locator("#sessions-sheet .fs-new").first()).toContainText(
      "New session with",
    );
    // the days and titles follow the day the fixtures were installed
    await expect(page.locator("#sessions-sheet")).toHaveScreenshot("sessions-sheet.png", {
      ...EXACT,
      mask: [page.locator("#sessions-sheet .ghead, #sessions-sheet .rday, #sessions-sheet .rtitle")],
    });
  });

  // R-0347
  test("a search that matches nothing says so, in those words", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator("#sessions-sheet .fs-search input").fill("zzzzz-no-such-session");
    await expect(page.locator(".fs-hint")).toHaveText("No sessions match");
  });

  // R-0095
  test("tapping the scrim closes it", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    await page.locator("#sessions-scrim").click({ position: { x: 195, y: 20 } });
    await page.waitForTimeout(400);
    await expect(page.locator("#sessions-sheet")).toBeHidden();
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

test.describe("the rows of the sessions sheet", () => {
  test.use({ storageState: stateFor("hostile") });

  const rows = (page: Page) =>
    page.locator("#sessions-sheet .fs-body .row").evaluateAll((all) =>
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

  // R-0096
  test("are a plain list: one column, none laid over another", async ({ page }) => {
    // every fixture holds one session, so the list is given three of it
    await page.route(/\/app\/sessions(\?.*)?$/, async (route) => {
      if (route.request().method() !== "GET") return route.continue();
      const real = await (await route.fetch()).json();
      const more = real.flatMap((s: { id: number }) =>
        [0, 1, 2].map((i) => ({ ...s, id: s.id + i * 100000 })),
      );
      await route.fulfill({ json: more });
    });
    await settle(page);
    await openSheet(page);
    await expect(page.locator("#sessions-sheet .fs-body .row")).toHaveCount(3);
    const all = await rows(page);
    expect(all.length).toBeGreaterThan(0);
    expect(new Set(all.map((r) => `${r.left} ${r.width}`)).size).toBe(1);
    all.slice(1).forEach((r, i) => expect(r.top).toBeGreaterThanOrEqual(all[i].bottom - 1));
  });

  // R-0096
  test("are not dressed as stacked cards: no offset, tilt or card behind", async ({ page }) => {
    await settle(page);
    await openSheet(page);
    const all = await rows(page);
    expect(all.length).toBeGreaterThan(0);
    expect(all.filter((r) => r.transform !== "none" || r.cards)).toEqual([]);
  });
});
