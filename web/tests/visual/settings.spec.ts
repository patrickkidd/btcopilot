import { expect, test, type Page } from "@playwright/test";
import { EXACT, flask, stateFor, username } from "./setup";

/** The settings stack: the avatar in the title row, and the pages it pushes.
 * Every value has one home, and the chat view's speak-replies row is the one
 * named shortcut onto the same value. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(600);
};

const openSettings = async (page: Page) => {
  await page.locator("#account").click();
  await expect(page.locator('.sn-pane[data-page="root"]')).toBeVisible();
  await page.waitForTimeout(300);
};

test.describe("the settings stack", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0089, R-0234
  test("the avatar sits in the title row at the ruled size", async ({ page }) => {
    await settle(page);
    const avatar = page.locator("#account");
    const inTitle = await avatar.evaluate((node) => !!node.closest(".titlerow"));
    expect(inTitle).toBe(true);
    const box = (await avatar.boundingBox())!;
    expect(Math.round(box.width)).toBe(44);
    expect(Math.round(box.height)).toBe(44);
  });

  // R-0098
  test("it opens on Account with the ruled rows in the ruled order", async ({
    page,
  }) => {
    await settle(page);
    await openSettings(page);
    await expect(page.locator("#title")).toHaveText("Account");
    const labels = await page.locator(".sn-pane.in .sn-lbl").allTextContents();
    expect(labels).toEqual([
      "Coach",
      "Appearance",
      "Your diagrams",
      "Plan and licenses",
    ]);
    await expect(page.locator(".sn-out")).toHaveText("Sign out");
    await expect(page.locator(".sn-foot")).toHaveText("Family Diagram · beta");
    await expect(page.locator('.sn-pane[data-page="root"]')).toHaveScreenshot(
      "settings-root.png",
      EXACT,
    );
  });

  // R-0004
  test("how often the coach messages first reads as a most, never a schedule", async ({
    page,
  }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-pane.in .sn-row.push", { hasText: "Coach" }).click();
    const choices = page.locator(
      '.sn-pane.in .sn-row:has-text("messages first") .sn-seg button',
    );
    const hint = page.locator(".sn-pane.in .sn-hint");
    await expect(choices).toHaveText(["never", "at most monthly", "at most weekly"]);
    // each choice's words fit inside it on a phone
    expect(
      await choices.evaluateAll((all) => all.filter((b) => b.scrollWidth > b.clientWidth).length),
    ).toBe(0);
    await choices.nth(2).click();
    await expect(hint).toHaveText(
      "Never more than once a week, and only when the coach notices a pattern in " +
        "your family's events or follows up on something you agreed to.",
    );
    await choices.nth(0).click();
    await expect(hint).toHaveText("The coach never messages first unless you ask it to.");
  });

  // R-0098
  test("a row pushes its own page and the chevron pops it", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-row.push").first().click();
    await expect(page.locator("#title")).toHaveText("Coach");
    await expect(page.locator('.sn-pane[data-page="coach"]')).toBeVisible();
    await page.locator("#settings-back").click();
    await page.waitForTimeout(300);
    await expect(page.locator("#title")).toHaveText("Account");
  });

  // R-0223, R-0281
  test("the back chevron on the root page closes the stack", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    await page.locator("#settings-back").click();
    await page.waitForTimeout(300);
    await expect(page.locator(".sn-stack")).toBeHidden();
    // the title row names the family the app is on, not a stock phrase
    await expect(page.locator("#title")).toHaveText("FD-362 visual fixture");
  });

  // R-0103
  test("speak replies is a switch of the ruled size, not a checkbox", async ({
    page,
  }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-row.push").first().click();
    await page.waitForTimeout(300);
    const box = (await page.locator(".sw").boundingBox())!;
    expect(Math.round(box.width)).toBe(51);
    expect(Math.round(box.height)).toBe(31);
    expect(await page.locator(".sn-pane.in input[type=checkbox]").count()).toBe(0);
  });

  // R-0101
  test("the chat row and the coach page write the same speak value", async ({
    page,
  }) => {
    await settle(page);
    const row = page.locator("#speak");
    const before = await row.isChecked();
    await row.setChecked(!before);
    await page.waitForTimeout(500);

    await openSettings(page);
    await page.locator(".sn-row.push").first().click();
    await page.waitForTimeout(300);
    await expect(page.locator(".sw")).toHaveAttribute(
      "aria-checked",
      String(!before),
    );

    await page.locator(".sw").click();
    await page.waitForTimeout(500);
    await page.locator("#settings-back").click();
    await page.locator("#settings-back").click();
    await page.waitForTimeout(400);
    expect(await row.isChecked()).toBe(before);
  });

  // R-0099
  test("the profile page carries the three ruled fields", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    await page.locator(".sn-cell").click();
    await page.waitForTimeout(300);
    await expect(page.locator("#title")).toHaveText("Profile");
    const labels = await page
      .locator('.sn-pane[data-page="profile"] .sn-lbl')
      .allTextContents();
    expect(labels).toEqual([
      "first name",
      "last name",
      "birthdate",
      "email",
      "sign in",
    ]);
  });

  // R-0103
  test("nothing in the stack falls under the 44px floor", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    const small = await page.evaluate(() =>
      [
        ...document.querySelectorAll(
          ".sn-pane.in .sn-row, .sn-pane.in .sn-cell, .sn-pane.in button, .sn-pane.in input",
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
});

test.describe("the title row", () => {
  test.use({ storageState: stateFor("moves") });

  /** Where a box sits against the app frame. */
  const at = (page: Page, selector: string) =>
    page.evaluate((sel) => {
      const frame = document.querySelector(".app")!.getBoundingClientRect();
      const box = document.querySelector(sel)!.getBoundingClientRect();
      return {
        left: box.left - frame.left,
        right: frame.right - box.right,
        top: box.top - frame.top,
        middle: box.top + box.height / 2,
        bottom: box.bottom - frame.top,
        width: frame.width,
      };
    }, selector);

  // R-0089
  test("the view's title is at the upper left of the frame", async ({ page }) => {
    await settle(page);
    const title = await at(page, "#title");
    const picture = await at(page, ".pic");
    // nothing sits above it, it starts in the left quarter, and nothing
    // showing in its row starts to the left of it
    expect(title.bottom).toBeLessThanOrEqual(picture.top);
    expect(title.left).toBeLessThan(title.width / 4);
    const before = await page.evaluate(() => {
      const words = document.getElementById("title")!.getBoundingClientRect().left;
      return [...document.querySelectorAll<HTMLElement>(".titlerow > *")]
        .filter((n) => n.id !== "title" && n.offsetParent)
        .filter((n) => n.getBoundingClientRect().left < words)
        .map((n) => n.id);
    });
    expect(before).toEqual([]);
    await openSettings(page);
    // the account view names itself in the same place
    await expect(page.locator("#title")).toHaveText("Account");
    const account = await at(page, "#title");
    expect(Math.abs(account.top - title.top)).toBeLessThanOrEqual(1);
    expect(account.left).toBeLessThan(account.width / 4);
  });

  // R-0089
  test("the account button is at the upper right, on the title's row", async ({ page }) => {
    await settle(page);
    const avatar = await at(page, "#account");
    const title = await at(page, "#title");
    const picture = await at(page, ".pic");
    expect(avatar.right).toBeLessThan(avatar.width / 4);
    expect(avatar.bottom).toBeLessThanOrEqual(picture.top);
    expect(Math.abs(avatar.middle - title.middle)).toBeLessThanOrEqual(2);
  });
});

test.describe("one home for every setting", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0101
  test("no row is offered on two settings pages", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    const rows = page.locator('.sn-pane[data-page="root"] .sn-row.push');
    const count = await rows.count();
    expect(count).toBeGreaterThan(1);
    const seen = new Map<string, string>();
    const twice: string[] = [];
    for (let i = 0; i < count; i++) {
      await page.locator('.sn-pane[data-page="root"] .sn-row.push').nth(i).click();
      await page.waitForTimeout(350);
      const pane = page.locator(".sn-pane.in").last();
      const name = (await pane.getAttribute("data-page"))!;
      for (const label of await pane.locator(".sn-lbl").allTextContents()) {
        const other = seen.get(label.trim());
        if (other && other !== name) twice.push(`${label} on ${other} and ${name}`);
        seen.set(label.trim(), name);
      }
      await page.locator("#settings-back").click();
      await page.waitForTimeout(350);
    }
    expect(seen.size).toBeGreaterThan(0);
    expect(twice).toEqual([]);
  });
});

test.describe("the controls that were too small", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0102
  test("the account button, the speak-replies box and the settings headings read at size", async ({
    page,
  }) => {
    await settle(page);
    const avatar = (await page.locator("#account").boundingBox())!;
    expect(Math.round(avatar.width)).toBeGreaterThanOrEqual(44);
    expect(Math.round(avatar.height)).toBeGreaterThanOrEqual(44);
    const row = (await page.locator("#speakrow").boundingBox())!;
    expect(Math.round(row.height)).toBeGreaterThanOrEqual(44);
    const box = (await page.locator("#speak").boundingBox())!;
    expect(Math.round(box.width)).toBeGreaterThanOrEqual(24);
    expect(
      await page.locator("#speakrow span").evaluate((n) => parseFloat(getComputedStyle(n).fontSize)),
    ).toBeGreaterThanOrEqual(15);
    await openSettings(page);
    const heads = await page
      .locator(".sn-pane.in .sn-hd, .sn-pane.in .sn-lbl")
      .evaluateAll((all) => all.map((n) => parseFloat(getComputedStyle(n).fontSize)));
    expect(heads.length).toBeGreaterThan(0);
    expect(heads.filter((size) => size < 13)).toEqual([]);
  });
});

test.describe("your diagrams", () => {
  test.use({ storageState: stateFor("moves") });

  const OTHER = { id: 987654, name: "The other family" };

  /** The account as the server tells it, with a second diagram beside the
   * fixture's own; which one is current follows the last select. */
  const twoDiagrams = async (page: Page) => {
    let current: number | null = null;
    const selected: string[] = [];
    await page.route(/\/app\/diagrams\/\d+\/select$/, async (route) => {
      selected.push(route.request().url());
      current = Number(route.request().url().match(/diagrams\/(\d+)/)![1]);
      await route.fulfill({
        json: { ...OTHER, session_count: 0, last_activity: null, free: false, current: true, owned: true },
      });
    });
    await page.route(/\/app\/account$/, async (route) => {
      const real = await (await route.fetch()).json();
      const own = real.diagrams[0];
      current ??= own.id;
      const other = { ...OTHER, session_count: 0, last_activity: null, free: false, owned: true };
      await route.fulfill({
        json: {
          ...real,
          diagrams: [own, other].map((d) => ({ ...d, current: d.id === current })),
        },
      });
    });
    return selected;
  };

  const openDiagrams = async (page: Page) => {
    await openSettings(page);
    await page.locator('.sn-pane[data-page="root"] .sn-row.push', { hasText: "Your diagrams" }).click();
    await expect(page.locator('.sn-pane[data-page="diagrams"]')).toBeVisible();
    await page.waitForTimeout(300);
  };

  // R-0175
  test("tapping a diagram's row opens that diagram", async ({ page }) => {
    const selected = await twoDiagrams(page);
    await settle(page);
    await openDiagrams(page);
    await page.locator('.sn-pane[data-page="diagrams"] .sn-row', { hasText: OTHER.name }).click();
    await expect(page.locator(".sn-stack")).toBeHidden();
    expect(selected).toHaveLength(1);
    expect(selected[0]).toContain(`/diagrams/${OTHER.id}/select`);
    await expect(page.locator("#title")).toHaveText(OTHER.name);
  });

  // R-0175
  test("only one diagram is open at a time", async ({ page }) => {
    await twoDiagrams(page);
    await settle(page);
    await openDiagrams(page);
    const ticks = () =>
      page
        .locator('.sn-pane[data-page="diagrams"] .sn-row')
        .evaluateAll((rows) =>
          rows
            .filter((r) => r.querySelector(".sn-tick")?.textContent?.trim())
            .map((r) => r.querySelector(".sn-t")?.textContent),
        );
    expect(await ticks()).toEqual(["FD-362 visual fixture"]);
    await page.locator('.sn-pane[data-page="diagrams"] .sn-row', { hasText: OTHER.name }).click();
    await expect(page.locator(".sn-stack")).toBeHidden();
    await openDiagrams(page);
    expect(await ticks()).toEqual([OTHER.name]);
  });
});

test.describe("opening the account view", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0225
  test("leaves the chat on screen underneath while the page covers it", async ({ page }) => {
    await settle(page);
    await openSettings(page);
    const chat = page.locator("#chat-screen");
    expect(await chat.evaluate((n) => getComputedStyle(n).display)).not.toBe("none");
    expect(await chat.evaluate((n) => (n as HTMLElement).hidden)).toBe(false);
    const box = (await chat.boundingBox())!;
    expect(box.height).toBeGreaterThan(100);
  });

  // R-0225
  test("slides the page in over the content rather than cutting to it", async ({ page }) => {
    await settle(page);
    await page.locator("#account").click();
    const pane = page.locator('.sn-pane[data-page="root"]');
    await expect(pane).toBeAttached();
    const moving = await pane.evaluate((n) => {
      const style = getComputedStyle(n);
      return {
        property: style.transitionProperty,
        seconds: parseFloat(style.transitionDuration),
      };
    });
    expect(moving.property).toContain("transform");
    expect(moving.seconds).toBeGreaterThan(0.1);
    // part way through, the page has not yet arrived and the chat still shows
    await page.waitForTimeout(40);
    const midway = await page.evaluate(() => {
      const pane = document.querySelector('.sn-pane[data-page="root"]')!.getBoundingClientRect();
      const frame = document.querySelector(".app")!.getBoundingClientRect();
      const chat = document.getElementById("chat-screen")!;
      return { offset: pane.left - frame.left, chat: getComputedStyle(chat).display };
    });
    expect(midway.offset).toBeGreaterThan(1);
    expect(midway.chat).not.toBe("none");
    await page.waitForTimeout(400);
    // it lands on the content area: the chat, and on a wide window the lists
    // pinned beside it (R-0352)
    const landed = (await pane.boundingBox())!;
    const content = (await page.locator("#chat-split").boundingBox())!;
    expect(Math.round(landed.x - content.x)).toBe(0);
  });

  // R-0225
  test("once landed, the page covers the whole content area under the title row", async ({
    page,
  }) => {
    await settle(page);
    await openSettings(page);
    const cover = await page.evaluate(() => {
      const pane = document.querySelector(".sn-pane.in")!.getBoundingClientRect();
      // the chat, and on a wide window the lists pinned beside it (R-0352)
      const chat = document.getElementById("chat-split")!.getBoundingClientRect();
      return {
        left: pane.left - chat.left,
        right: chat.right - pane.right,
        top: pane.top - chat.top,
        bottom: chat.bottom - pane.bottom,
        ground: getComputedStyle(document.querySelector(".sn-pane.in")!).backgroundColor,
      };
    });
    expect(Math.abs(cover.left)).toBeLessThanOrEqual(1);
    expect(Math.abs(cover.right)).toBeLessThanOrEqual(1);
    // it may start under the title row, which stays drawn over it
    expect(cover.top).toBeLessThanOrEqual(1);
    expect(cover.bottom).toBeLessThanOrEqual(1);
    expect(cover.ground).not.toBe("rgba(0, 0, 0, 0)");
  });
});

/** Coding, the meeting and the replies picked blind hang on no family, so
 * they sit in the account view, each for whoever does it. */
test.describe("the coding and quality sections", () => {
  test.use({ storageState: stateFor("empty") });
  const roles = (...names: string[]) =>
    flask("admin", "run", "--", "users", "roles", username("empty"), ...names, "--yes");
  const heads = (page: Page) => page.locator(".sn-pane.in .sn-hd").allTextContents();
  const row = (page: Page, label: string) =>
    page.locator(".sn-pane.in .sn-row.push", { hasText: label });
  const as = async (page: Page, ...names: string[]) => {
    roles(...names, "subscriber");
    await page.goto("/app/");
    await openSettings(page);
  };
  test.afterAll(() => roles("subscriber"));

  // R-0259, R-0265, R-0599
  test("a subscriber sees neither, an auditor sees Coding, and an admin sees Coding with the meeting and Quality", async ({
    page,
  }) => {
    await as(page);
    expect(await heads(page)).toEqual([]);

    await as(page, "auditor");
    expect(await heads(page)).toEqual(["Coding"]);
    await expect(row(page, "Your coding task")).toHaveCount(1);
    await expect(row(page, "Next meeting")).toHaveCount(0);

    await as(page, "admin");
    expect(await heads(page)).toEqual(["Coding", "Quality"]);
    await expect(row(page, "Next meeting")).toHaveCount(1);
    await expect(row(page, "Better reply")).toHaveCount(1);
    await expect(page.locator(".sn-pane.in .sn-hint")).toHaveText(
      "Pick the better of two coach replies",
    );
    await row(page, "Your coding task").click();
    await expect(page.locator("#task-screen")).toBeVisible();
    await expect(page.locator(".sn-pane.in")).toHaveCount(0);
  });

  // R-0267
  test("an admin puts another family's session on the agenda from the meeting page, and placing the cut returns there", async ({
    page,
  }) => {
    await as(page, "admin");
    await row(page, "Next meeting").click();
    await expect(page.locator("#agenda-screen")).toBeVisible();
    await page.locator(".tb-add").click();
    await expect(page.locator("#title")).toHaveText("Pick a session");
    await page.locator("#coding-back").click();
    await expect(page.locator("#agenda-screen .tb-add")).toBeVisible();

    await page.locator(".tb-add").click();
    // said only in the moves fixture's session, never in this admin's family,
    // and inside a chip, which the line shows as its words
    await page.locator(".tb-words").fill("altogether");
    const picked = page.locator(".tb-pick");
    await expect(picked).toHaveCount(1);
    const line = await picked.locator(".sn-s").last().innerText();
    expect(line).toContain("stopped speaking to him altogether.");
    expect(line).not.toContain("[[");
    await picked.click();
    await expect(page.locator("#cut-screen")).toBeVisible();
    await expect(page.locator("#cut-chat")).toContainText("walk me through it");
    const session = await page.locator("#title").innerText();

    await page.locator(".ct-go").click();
    await expect(page.locator("#agenda-screen")).toBeVisible();
    const cut = page.locator(".tb-cut", { hasText: session });
    await expect(cut).toHaveCount(1);
    // taken back off, so the fixtures install again over this record
    await cut.locator(".pl-btn").click();
    await expect(cut).toHaveCount(0);
  });
});

test.describe("the concept pages row", () => {
  test.use({ storageState: stateFor("empty") });
  const roles = (...names: string[]) =>
    flask("admin", "run", "--", "users", "roles", username("empty"), ...names, "--yes");
  const row = (page: Page) =>
    page.locator(".sn-pane.in .sn-row.push", { hasText: "Concept pages" });
  test.afterAll(() => roles("subscriber"));

  // R-0541, R-0567
  test("shows to an auditor and an admin, opens the pages, and is absent for a subscriber", async ({
    page,
  }) => {
    for (const role of ["auditor", "admin"]) {
      roles(role, "subscriber");
      await page.goto("/app/");
      await openSettings(page);
      await expect(row(page)).toHaveCount(1);
    }
    const [tab] = await Promise.all([page.waitForEvent("popup"), row(page).click()]);
    expect(new URL(tab.url()).pathname).toBe("/app/theory");
    await tab.close();

    roles("subscriber");
    await page.goto("/app/");
    await openSettings(page);
    await expect(row(page)).toHaveCount(0);
  });
});
