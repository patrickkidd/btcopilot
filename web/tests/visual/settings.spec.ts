import { expect, test, type Page } from "./fixtures";
import { EXACT, flask, placeCut, shell, stateFor, toTheirDiagram, backToMine, username, boxOf, inside } from "./setup";

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
    const box = await boxOf(avatar);
    expect(Math.round(box.width)).toBe(44);
    expect(Math.round(box.height)).toBe(44);
  });

  // R-0098, R-0631
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
      "Diagrams",
      "Your Plan",
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
    const box = await boxOf(page.locator(".sw"));
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

  // R-0102, R-0631
  test("the account button, the speak-replies box and the settings headings read at size", async ({
    page,
  }) => {
    await settle(page);
    const avatar = await boxOf(page.locator("#account"));
    expect(Math.round(avatar.width)).toBeGreaterThanOrEqual(44);
    expect(Math.round(avatar.height)).toBeGreaterThanOrEqual(44);
    const row = await boxOf(page.locator("#speakrow"));
    expect(Math.round(row.height)).toBeGreaterThanOrEqual(44);
    const box = await boxOf(page.locator("#speak"));
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
   * fixture's own; which one is current follows the last select. The second
   * diagram is only in the page, so what is read by its id is the fixture's
   * own record, thread and sittings. */
  const twoDiagrams = async (page: Page) => {
    let current: number | null = null;
    const selected: string[] = [];
    await page.route(new RegExp(`\\?diagram_id=${OTHER.id}$`), async (route) =>
      route.fulfill({ response: await route.fetch({ url: route.request().url().split("?")[0] }) }),
    );
    await page.route(/\/app\/diagrams\/\d+\/select$/, async (route) => {
      selected.push(route.request().url());
      current = Number(route.request().url().match(/diagrams\/(\d+)/)![1]);
      await route.fulfill({
        json: { ...OTHER, session_count: 0, last_activity: null, free: false, current: true, owned: true, access: "own", owner: "Unit Tester" },
      });
    });
    await page.route(/\/app\/account$/, async (route) => {
      const real = await (await route.fetch()).json();
      const own = real.diagrams[0];
      current ??= own.id;
      const other = { ...OTHER, session_count: 0, last_activity: null, free: false, owned: true, access: "own", owner: "Unit Tester" };
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
    await page.locator('.sn-pane[data-page="root"] .sn-row.push', { hasText: "Diagrams" }).click();
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

  test.describe("with a Family view", () => {
    test.use({ storageState: stateFor("play") });

    // R-0691, R-0175
    test("the Family view's book reads its passages again for the diagram opened next", async ({ page }) => {
      await twoDiagrams(page);
      await page.route(/\/app\/case-report-passages(\?.*)?$/, (route) => {
        const other = route.request().url().includes(`diagram_id=${OTHER.id}`);
        return route.fulfill({ json: { family: [{ text: other ? "The other family's passage" : "The first family's passage", by: "Kerr & Bowen, Family Evaluation, ch. 10" }] } });
      });
      await settle(page);
      const sheet = page.locator("#chat-screen .fs-sheet.bk");
      const book = async (passage: string) => {
        await page.locator("#cap-family").click();
        await expect(page.locator("#pbp")).toBeVisible();
        await page.locator("#pbp .path .book").click();
        await expect(sheet).toHaveClass(/in/);
        await expect(sheet.locator("blockquote")).toHaveText(passage);
        await page.keyboard.press("Escape");
        await expect(sheet).not.toHaveClass(/in/);
        await page.goBack();
        await expect(page.locator("#pbp")).toBeHidden();
      };
      await book("The first family's passage");
      await openDiagrams(page);
      await page.locator('.sn-pane[data-page="diagrams"] .sn-row', { hasText: OTHER.name }).click();
      await expect(page.locator(".sn-stack")).toBeHidden();
      await expect(page.locator("#title")).toHaveText(OTHER.name);
      await book("The other family's passage");
    });
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

test.describe("an admin finds a person on the diagrams view", () => {
  test.use({ storageState: stateFor("longname") });

  /** The admin role, and afterwards nothing the walk opened. */
  const as = (roles: string) =>
    shell(
      [
        "from btcopilot.extensions import db",
        "from btcopilot.models import User",
        `me = User.query.filter_by(username="${username("longname")}").one()`,
        `me.roles = "${roles}"`,
        "me.current_diagram_id = None",
        "db.session.commit()",
        "",
      ].join("\n"),
    );

  const openDiagrams = async (page: Page) => {
    await page.goto("/app/account/diagrams");
    await expect(page.locator('.sn-pane[data-page="diagrams"]')).toBeVisible();
  };

  test.afterAll(() => as("subscriber"));

  // R-0175, R-0629, R-0630
  test("searching a name lists the person, and tapping their diagram opens it read-only", async ({ page }) => {
    as("admin");
    await openDiagrams(page);
    const pane = page.locator('.sn-pane[data-page="diagrams"]');
    await pane.getByLabel("Find a person").fill("whitlock");
    const person = pane.locator(".sn-find .sn-row", { hasText: username("whitlock") });
    await expect(person).toBeVisible();
    await person.click();
    await expect(page.locator("#title")).toHaveText(/whitlock|Whitlock/i);
    const theirs = page.locator(".sn-theirs .sn-row").first();
    const name = (await theirs.locator(".sn-t").textContent())!;
    await theirs.click();
    await expect(page.locator(".sn-stack")).toBeHidden();
    await expect(page.locator("#title")).toHaveText(name);

    await expect(page.locator("#viewing")).toBeVisible();
    await expect(page.locator("#chat .bub").first()).toBeVisible();
    await expect(page.locator("#viewing-who")).toHaveText(/^Viewing .+'s diagram, read-only$/);
    await expect(page.locator("#composer")).toBeHidden();
    await expect(page.locator("#send")).toBeHidden();
    await expect(page.locator("#viewing-cut")).toHaveText("Select a cut");
    await expect(page.locator("#cut-strip")).toBeHidden();

    await page.locator("#sessions-open").click();
    const sitting = page.locator("#sessions-sheet .row").first();
    await expect(sitting.locator(".rmore")).toBeHidden();
    await sitting.locator(".rsub").click();
    await expect(page.locator("#sessions-sheet")).toBeHidden();
    await expect(page.locator("#viewing")).toBeVisible();

    await page.locator("#viewing-back").click();
    await expect(page.locator("#viewing")).toBeHidden();
    await expect(page.locator("#title")).not.toHaveText(name);
    await expect(page.locator("#composer")).toBeVisible();
  });

  // R-0630, R-0631
  test("own diagrams give way to the people found and come back when the search is cleared", async ({ page }) => {
    as("admin");
    await openDiagrams(page);
    const pane = page.locator('.sn-pane[data-page="diagrams"]');
    const own = pane.locator(".sn-hd", { hasText: /Diagrams|Cases/ });
    await expect(own).toBeVisible();
    const field = pane.getByLabel("Find a person");
    await field.fill(username("longname"));
    const person = pane.locator(".sn-find .sn-row", { hasText: username("longname") });
    await expect(person).toBeVisible();
    await expect(own).toBeHidden();
    await person.click();
    await expect(page.locator(".sn-theirs .sn-row").first()).toBeVisible();
    await expect(pane).toHaveClass(/under/);
    await page.locator("#settings-back").click();
    await expect(pane).not.toHaveClass(/under/);
    await expect(field).toHaveValue(username("longname"));
    await expect(person).toBeVisible();
    await expect(own).toBeHidden();
    await field.fill("");
    await expect(own).toBeVisible();
    await expect(pane.locator(".sn-find .sn-row")).toHaveCount(0);
  });

  // R-0175
  test("someone who is not an admin sees no search for people", async ({ page }) => {
    as("subscriber");
    await openDiagrams(page);
    await expect(page.locator('.sn-pane[data-page="diagrams"] .sn-find')).toHaveCount(0);
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
    const box = await boxOf(chat);
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
    const landed = await boxOf(pane);
    const content = await boxOf(page.locator("#chat-split"));
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

  // R-0259, R-0265, R-0599, R-0631
  test("a subscriber sees neither, an auditor sees Coding, and an admin sees Coding with the meeting and Quality", async ({
    page,
  }) => {
    await as(page);
    expect(await heads(page)).toEqual(["Data"]);

    await as(page, "auditor");
    expect(await heads(page)).toEqual(["Data", "Coding"]);
    await expect(row(page, "Your coding task")).toHaveCount(1);
    await expect(row(page, "Next meeting")).toHaveCount(0);

    await as(page, "admin");
    expect(await heads(page)).toEqual(["Data", "Coding", "Quality"]);
    await expect(row(page, "Next meeting")).toHaveCount(1);
    await expect(row(page, "Better replies")).toHaveCount(1);
    await expect(page.locator(".sn-pane.in .sn-hint")).toHaveText(
      "Pick the better of two coach replies",
    );
    await row(page, "Your coding task").click();
    await expect(page.locator(".sn-pane.in #task-screen")).toBeVisible();
    await page.locator("#settings-back").click();
    await expect(page.locator(".sn-pane.in")).toHaveAttribute("data-page", "root");
  });

  // R-0259, R-0265, R-0599
  test("the task, the meeting and the better replies each open on the account view's stack, and back returns to the account view", async ({
    page,
  }) => {
    await as(page, "admin");
    for (const [label, screen, title] of [
      ["Your coding task", "task-screen", null],
      ["Next meeting", "agenda-screen", "Next meeting"],
      ["Better replies", "pairs-screen", "Better replies"],
    ] as const) {
      await row(page, label).click();
      const top = page.locator(".sn-pane.in:not(.under)");
      await expect(top).toHaveAttribute("data-page", screen);
      await expect(page.locator("#settings-back")).toBeVisible();
      if (title) await expect(page.locator("#title")).toHaveText(title);
      await page.locator("#settings-back").click();
      await expect(page.locator(".sn-pane.in")).toHaveAttribute("data-page", "root");
      await expect(page.locator("#title")).toHaveText("Account");
    }
  });

  // R-0259, R-0271
  test("the coding screen opened from the task card is titled with the conversation and how far it runs, all of it inside the title row", async ({
    page,
  }) => {
    await as(page, "auditor");
    const coded = await page.evaluate(
      () => (window as unknown as { BOOTSTRAP: { diagram: { id: number } } }).BOOTSTRAP.diagram.id,
    );
    const session = "The long conversation about the move to the coast";
    await page.route(
      (url) => url.pathname === "/review/tasks",
      (route) =>
        route.fulfill({
          json: {
            task: { kind: "code", cut_id: 1, coding_id: 7, meeting_date: null, title: `Code ${session}`, detail: "", ready: true },
            done: [],
          },
        }),
    );
    await page.route(
      (url) => url.pathname === "/review/codings/7/thread",
      (route) =>
        route.fulfill({
          json: { coding_id: 7, cut_id: 1, diagram_id: coded, done_at: null, meeting_date: null, session, cut_day: "Sep 29", agreed: null, turns: [] },
        }),
    );
    await row(page, "Your coding task").click();
    await page.locator(".sn-pane.in #task-screen .addbtn").click();
    await expect(page.locator("#coding-screen")).toBeVisible();
    const title = page.locator("#title");
    const name = title.locator(".ttl-name");
    const tail = title.locator(".ttl-tail");
    const cut = () => name.evaluate((el) => el.scrollWidth > el.clientWidth);
    const size = page.viewportSize()!;
    for (const [width, shortened] of [[390, true], [1024, false]] as const) {
      await page.setViewportSize({ width, height: size.height });
      await expect(name).toHaveText(session);
      await expect(tail).toHaveText(" · up to Sep 29");
      await inside(title, page.locator(".titlerow"));
      await inside(tail, title);
      const [end, next] = [await boxOf(title), await boxOf(page.locator("#coding-info"))];
      expect(end.x + end.width).toBeLessThanOrEqual(next.x);
      // at phone width the name gives way with an ellipsis and the tail stays
      expect(await cut()).toBe(shortened);
      await expect(name).toHaveCSS("text-overflow", "ellipsis");
    }
    await page.setViewportSize(size);
  });

  // R-0250, R-0258
  test("two cuts on one meeting date are one meeting with one run button, and its page says who has submitted each", async ({
    page,
  }) => {
    await as(page, "admin");
    const cut = (id: number, session: string) => ({
      id,
      sitting_id: 900 + id,
      start_statement_id: 1,
      end_statement_id: 4,
      meeting_date: "2026-10-06",
      vote_opened_at: "2026-09-29T19:22:37",
      ratified_at: null,
      nudged_at: null,
      session,
      owner: session,
      end_order: 4,
      cut_day: "Sep 29",
      started: id === 1,
      agreement: null,
    });
    const cuts = [cut(1, "The Sunday call"), cut(2, "The move to the coast")];
    const line = (user_id: number, name: string, state: string) => ({
      user_id,
      name,
      state,
      closed_out: false,
    });
    await page.route(
      (url) => url.pathname === "/review/cuts",
      (route) => route.fulfill({ json: cuts }),
    );
    const sitting = { id: 901, title: "", started: "2026-09-29T19:00:00", previous_started: null, first_statement_id: 1 };
    const turn = (id: number) => ({ id, order: id, sitting_id: 901, client: true, text: "", day: "Sep 29" });
    await page.route(
      (url) => url.pathname === "/review/turns",
      (route) => route.fulfill({ json: { sittings: [sitting], turns: [turn(1), turn(4)] } }),
    );
    await page.route(
      (url) => url.pathname === "/review/coders",
      (route) => {
        const one = new URL(route.request().url()).searchParams.get("cut_id") === "1";
        route.fulfill({
          json: [line(1, "you", one ? "done" : "not started"), line(2, "AB", "not started")],
        });
      },
    );
    await row(page, "Next meeting").click();
    await expect(page.locator("#agenda-body .tb-cut")).toHaveCount(2);
    await expect(page.locator("#agenda-body .tb-when")).toHaveCount(1);
    await expect(page.locator("#agenda-body .tb-meet")).toHaveCount(1);

    await page.locator(".tb-meet").click();
    await expect(page.locator(".sn-pane.in:not(.under)")).toHaveAttribute("data-page", "meet-screen");
    await expect(page.locator("#title")).toContainText("Meeting");
    const submitted = page.locator("#meet-body .tb-run");
    await expect(submitted).toHaveCount(1);
    await expect(submitted).toContainText("The Sunday call");
    await expect(submitted).toContainText("Submitted: you");
    await expect(submitted).toContainText("Not submitted: AB");
    await expect(page.locator("#meet-body .sn-hint")).toHaveText(["No coder has submitted yet"]);
    await page.locator("#settings-back").click();
    await expect(page.locator(".sn-pane.in:not(.under)")).toHaveAttribute("data-page", "agenda-screen");
  });

  // R-0629, R-0631
  test("an admin selects a cut in someone else's chat from Next meeting, and placing it returns there", async ({
    page,
  }, testInfo) => {
    await as(page, "admin");
    await row(page, "Next meeting").click();
    await expect(page.locator("#agenda-screen")).toBeVisible();
    await expect(page.locator(".tb-add")).toHaveText("Select a cut for the agenda");
    await toTheirDiagram(page, username("sittings"));
    await expect(page.locator("#cut-say")).toHaveText("Selecting a cut · tap the first line, then the last");
    await expect(page.locator("#viewing-cut")).toBeHidden();
    await expect(page.locator("#inbar")).toBeHidden();

    await placeCut(page);
    await expect(page.locator(".sn-pane.in:not(.under)")).toHaveAttribute("data-page", "agenda-screen");
    const cut = page.locator(".tb-cut").last();
    await expect(cut.locator(".sn-s")).toHaveText(/^[\w ]+ \d{4} · \d+ sittings?$/);
    await expect(cut).not.toContainText("up to turn");
    // taken back off, so the fixtures install again over this record
    const before = await page.locator(".tb-cut").count();
    await cut.locator(".pl-btn").click();
    const ask = page.locator(".ag.cf-sheet");
    await expect(ask.locator(".cf-t")).toHaveText("Take this cut off the agenda?");
    await ask.locator("button", { hasText: "Keep it" }).click();
    await expect(ask).not.toHaveClass(/\bin\b/);
    await expect(page.locator(".tb-cut")).toHaveCount(before);
    if (testInfo.project.name === "desktop") {
      await cut.locator(".pl-btn").click();
      await expect(ask).toHaveClass(/\bin\b/);
      await page.mouse.click(10, 300);
      await expect(ask).not.toHaveClass(/\bin\b/);
    }
    await cut.locator(".pl-btn").click();
    await page.locator(".ag.cf-sheet button", { hasText: "Take it off" }).click();
    await expect(page.locator(".tb-cut")).toHaveCount(before - 1);
    await backToMine(page);
  });
});

test.describe("the Auditor's Coding Guide row", () => {
  test.use({ storageState: stateFor("empty") });
  const roles = (...names: string[]) =>
    flask("admin", "run", "--", "users", "roles", username("empty"), ...names, "--yes");
  const row = (page: Page) =>
    page.locator(".sn-pane.in .sn-row.push", { hasText: "Auditor's Coding Guide" });
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
    await row(page).click();
    const frame = page.locator('.sn-pane.in iframe[title="Auditor\'s Coding Guide"]');
    await expect(frame).toBeVisible();
    await expect(page.locator("#title")).toHaveText("Auditor's Coding Guide");
    expect(await frame.getAttribute("src")).toBe("/app/theory");
    await page.locator("#settings-back").click();
    await expect(page.locator(".sn-pane.in")).toHaveAttribute("data-page", "root");

    roles("subscriber");
    await page.goto("/app/");
    await openSettings(page);
    await expect(row(page)).toHaveCount(0);
  });
});

test.describe("the Conversation Feedback switch", () => {
  test.use({ storageState: stateFor("empty") });
  const roles = (...names: string[]) =>
    flask("admin", "run", "--", "users", "roles", username("empty"), ...names, "--yes");
  test.afterAll(() => roles("subscriber"));

  // R-0637, R-0642, R-0643
  test("an admin sees it with what it costs, and turning it on asks first", async ({ page }) => {
    roles("admin", "subscriber");
    const patched: unknown[] = [];
    await page.route(/\/app\/preferences$/, async (route) => {
      const prefs = await (await page.request.get("/app/preferences")).json();
      const cost = { per_turn_usd: 0.19, month_usd: 3.42 };
      if (route.request().method() !== "PATCH")
        return route.fulfill({ json: { ...prefs, shadow_models: [], shadow_cost: cost } });
      patched.push(route.request().postDataJSON());
      await route.fulfill({ json: { ...prefs, shadow_models: prefs.shadow_candidates, shadow_cost: cost } });
    });
    await page.goto("/app/");
    await openSettings(page);
    await page.locator(".sn-pane.in .sn-row.push", { hasText: "Coach" }).click();
    const pane = page.locator('.sn-pane.in[data-page="coach"]');
    await expect(pane.locator(".sn-hd", { hasText: "Admin" })).toBeVisible();
    await expect(pane.locator(".sn-row", { hasText: "Extra cost" })).toContainText("about 19¢ a turn");
    await expect(pane.locator(".sn-row", { hasText: "Spent this month" })).toContainText("$3.42");
    await page.waitForTimeout(300);
    await expect(pane).toHaveScreenshot("settings-shadows.png");

    const toggle = () => page.locator('.sn-pane.in[data-page="coach"] [role="switch"][aria-label="Conversation Feedback"]');
    await toggle().click();
    const sheet = page.locator(".fs-sheet.sh");
    await expect(sheet).toBeVisible();
    await expect(sheet.locator(".cf-p")).toContainText("It costs Patrick money.");
    await sheet.getByRole("button", { name: "Cancel" }).click();
    await expect(sheet).toBeHidden();
    expect(patched).toEqual([]);
    const lapse = pane.locator(".sn-hint", { hasText: "Turns off" });
    await expect(lapse).toHaveCount(0);

    await toggle().click();
    await sheet.getByRole("button", { name: "Turn on" }).click();
    await expect(toggle()).toHaveAttribute("aria-checked", "true");
    expect(patched).toEqual([{ shadow_models: ["sonnet"] }]);
    await expect(lapse).toHaveText("Turns off 5 minutes after the coach's last reply or your last vote");
  });
});
