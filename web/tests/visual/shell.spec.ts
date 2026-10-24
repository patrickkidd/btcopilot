import { expect, test, type Page } from "./fixtures";
import { pinned, stateFor } from "./setup";

/** The frame the app lives in: the title row at the top, the picture straight
 * under it, the phone's own furniture around it, and one size for every icon
 * button in it. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

/** Every icon button on screen: a button that carries a mark rather than
 * words, with its target and its drawn circle. The target is the button, or
 * the larger square round it where a small control reaches out to 44. */
const iconButtons = (page: Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll<HTMLButtonElement>("button")]
      // a mark is drawn or written: the picture's invisible tap targets carry
      // none, and a word is not a mark
      .filter((b) => (b.childElementCount || (b.textContent ?? "").trim()) && b.offsetParent)
      .filter((b) => !/[a-z]{2}/i.test(b.textContent ?? ""))
      .map((b) => {
        const box = b.getBoundingClientRect();
        const mark = getComputedStyle(b, "::before");
        const reach = (side: number, drawn: string) =>
          Math.round(Math.max(side, parseFloat(drawn) || 0));
        return {
          id: b.id || b.className,
          size: `${reach(box.width, mark.width)}x${reach(box.height, mark.height)}`,
          mark: mark.content === "none" ? null : `${parseFloat(mark.width)}x${parseFloat(mark.height)}`,
        };
      }),
  );

test.describe("the app frame", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0091
  test("the account, sessions, list and send buttons share one target, and all but the list one circle", async ({
    page,
  }) => {
    await settle(page);
    const found = await iconButtons(page);
    const shell = found.filter((b) =>
      ["account", "sessions-open", "menu-open", "send"].includes(b.id),
    );
    // a wide window draws no list button (R-0352); a reader with nothing in
    // the sessions sheet has no door to it
    const drawn = (await pinned(page))
      ? ["account", "send"]
      : ["account", "menu-open", "send"];
    expect(shell.map((b) => b.id).sort()).toEqual(drawn);
    expect(new Set(shell.map((b) => b.size))).toEqual(new Set(["44x44"]));
    // the list button is drawn the height of the chips it sits beside
    expect(
      new Set(shell.filter((b) => b.id !== "menu-open").map((b) => b.mark)),
    ).toEqual(new Set(["40x40"]));
  });

  // R-0091
  test("every icon button on the chat screen is a 44px target", async ({ page }) => {
    await settle(page);
    const found = await iconButtons(page);
    expect(found.length).toBeGreaterThan(3);
    expect(found.filter((b) => b.size !== "44x44")).toEqual([]);
  });

  // R-0093
  test("no header sits above the title row; the picture starts right under it", async ({
    page,
  }) => {
    await settle(page);
    const stack = await page.evaluate(() => {
      const frame = document.querySelector(".app")!.getBoundingClientRect();
      const title = document.querySelector(".titlerow")!.getBoundingClientRect();
      const picture = document.querySelector("#chat-screen .pic")!.getBoundingClientRect();
      return {
        headers: document.querySelectorAll("header, [role=banner]").length,
        titleTop: title.top - frame.top,
        gap: picture.top - title.bottom,
      };
    });
    expect(stack.headers).toBe(0);
    expect(stack.titleTop).toBeLessThanOrEqual(1);
    expect(Math.abs(stack.gap)).toBeLessThanOrEqual(1);
  });

  // R-0094
  test("the phone's own bars take the app's ground and the app runs edge to edge", async ({
    page,
  }) => {
    await settle(page);
    const chrome = await page.evaluate(() => {
      const meta = (name: string) =>
        [...document.querySelectorAll<HTMLMetaElement>(`meta[name="${name}"]`)].map((m) => ({
          content: m.content,
          media: m.media,
        }));
      return {
        theme: meta("theme-color"),
        viewport: meta("viewport")[0]?.content ?? "",
        capable: meta("apple-mobile-web-app-capable")[0]?.content,
        manifest: !!document.querySelector('link[rel="manifest"]'),
        ground: getComputedStyle(document.body).backgroundColor,
      };
    });
    expect(chrome.viewport).toContain("viewport-fit=cover");
    expect(chrome.capable).toBe("yes");
    expect(chrome.manifest).toBe(true);
    const light = chrome.theme.find((t) => t.media.includes("light"));
    expect(light).toBeTruthy();
    const hex = light!.content.replace("#", "");
    const rgb = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
    expect(chrome.ground).toBe(`rgb(${rgb.join(", ")})`);
  });

  // R-0275, R-0278
  test("the info button in the title row opens the coding guidelines", async ({ page }) => {
    await settle(page);
    const info = page.locator(".titlerow #coding-info");
    await expect(info).toHaveAttribute("aria-label", "Coding guidelines");
    // it shows on the coding screens, which no fixture reaches, and the
    // guidelines are read only by a coder, which no fixture is
    const rule = {
      id: 1, text: "Date a shift by when it began", source: {}, drafted_by: "human",
      flags: [], flagged: false, ratified_at: null, retired_at: null,
    };
    await page.route(/\/review\/rules$/, (route) => route.fulfill({ json: [rule] }));
    await info.evaluate((b) => ((b as HTMLElement).hidden = false));
    await info.click();
    await expect(page.locator("#rules-screen")).toBeVisible();
    await expect(page.locator("#rules-screen .ovt")).toHaveText("Coding guidelines");
    await expect(page.locator("#rules-body")).toContainText(rule.text);
  });

});

test.describe("the concept pages, read inside the app", () => {
  test.use({ storageState: stateFor("moves"), serviceWorkers: "block" });

  // R-0541, R-0567
  test("with no guidelines yet, the coding guidelines list the concept pages, each read inside the app", async ({
    page,
  }) => {
    await settle(page);
    // no fixture is a coder, and the pages are served to coders alone
    await page.evaluate(() => (window.BOOTSTRAP.user!.coder = true));
    await page.route(/\/review\/rules$/, (route) => route.fulfill({ json: [] }));
    // the pages link on to one another, as the guide's pages do
    const pages: Record<string, string> = {
      "/app/theory":
        '<h1>Concept pages: index</h1><a id="symptom" href="/app/theory/symptom">symptom</a> <a id="anxiety" href="/app/theory/anxiety">anxiety</a>',
      "/app/theory/symptom": '<h1>Symptom (S)</h1><a id="index" href="/app/theory">index</a>',
      "/app/theory/anxiety": "<h1>Anxiety (A)</h1>",
    };
    await page.route(/\/app\/theory/, (route) =>
      route.fulfill({ contentType: "text/html", body: pages[new URL(route.request().url()).pathname] }),
    );
    const info = page.locator(".titlerow #coding-info");
    await info.evaluate((b) => ((b as HTMLElement).hidden = false));
    await info.click();
    const body = page.locator("#rules-body");
    const rows = body.locator(".sn-row.push");
    await expect(body.locator(".sn-hd")).toHaveText(["Concept pages"]);
    await expect(rows).toHaveCount(12);
    await expect(rows.last()).toHaveText(/All concept pages/);
    await expect(body).not.toContainText("No coding guidelines yet");

    const frame = page.locator("#rules-screen > iframe");
    const inside = page.frameLocator("#rules-screen > iframe");
    const title = page.locator("#rules-title");
    await rows.first().click();
    await expect(frame).toBeVisible();
    expect(await frame.getAttribute("src")).toBe("/app/theory/symptom");
    // a page is named by its own heading, whichever way it was reached
    await expect(title).toHaveText("Symptom (S)");
    await expect(body).toBeHidden();
    expect(page.context().pages()).toHaveLength(1);
    await page.locator("#rules-close").click();
    await expect(frame).toHaveCount(0);
    await expect(title).toHaveText("Coding guidelines");

    // back steps one page at a time through the pages read, in the order
    // read, a page read twice included, then leaves for the list
    await rows.last().click();
    const steps = ["Concept pages: index", "Symptom (S)", "Concept pages: index", "Anxiety (A)"];
    await expect(title).toHaveText(steps[0]);
    await inside.locator("#symptom").click();
    await expect(title).toHaveText(steps[1]);
    await inside.locator("#index").click();
    await expect(title).toHaveText(steps[2]);
    await inside.locator("#anxiety").click();
    await expect(title).toHaveText(steps[3]);
    for (const back of [...steps].reverse().slice(1)) {
      await page.locator("#rules-close").click();
      await expect(inside.locator("h1")).toHaveText(back);
      await expect(title).toHaveText(back);
    }
    await page.locator("#rules-close").click();
    await expect(frame).toHaveCount(0);
    await expect(body).toBeVisible();
    await expect(title).toHaveText("Coding guidelines");
    await expect(page.locator("#rules-screen")).toBeVisible();
  });

  // R-0541, R-0567
  test("a concept link under a code opens its page inside the app, and back returns to the screen it was on", async ({
    page,
  }) => {
    await settle(page);
    await page.route(/\/app\/theory/, (route) =>
      route.fulfill({ contentType: "text/html", body: "<h1>Anxiety</h1>" }),
    );
    // the vote, the meeting and the coding draw these under a code, which no
    // fixture reaches; the markup is the one they draw
    await page.locator("#chat-split").evaluate((host) =>
      host.insertAdjacentHTML(
        "afterbegin",
        '<div class="concepts">read: <a href="/app/theory/anxiety">anxiety</a></div>',
      ),
    );
    await page.locator(".concepts a").click();
    const frame = page.locator('#rules-screen > iframe[title="Anxiety"]');
    await expect(frame).toBeVisible();
    expect(await frame.getAttribute("src")).toBe("/app/theory/anxiety");
    expect(page.context().pages()).toHaveLength(1);

    await page.locator("#rules-close").click();
    await expect(page.locator("#rules-screen")).toBeHidden();
    await expect(frame).toHaveCount(0);
    await expect(page.locator("#chat-split")).toBeVisible();
  });
});
