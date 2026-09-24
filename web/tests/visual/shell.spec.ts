import { expect, test, type Page } from "@playwright/test";
import { stateFor } from "./setup";

/** The frame the app lives in: the title row at the top, the picture straight
 * under it, the phone's own furniture around it, and one size for every icon
 * button in it. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

/** Every icon button on screen: a button that carries a mark rather than
 * words, with its target and its drawn circle. */
const iconButtons = (page: Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll<HTMLButtonElement>("button")]
      .filter((b) => b.offsetParent && !/[a-z]{2}/i.test(b.textContent ?? ""))
      .map((b) => {
        const box = b.getBoundingClientRect();
        const mark = getComputedStyle(b, "::before");
        return {
          id: b.id || b.className,
          size: `${Math.round(box.width)}x${Math.round(box.height)}`,
          mark: mark.content === "none" ? null : `${parseFloat(mark.width)}x${parseFloat(mark.height)}`,
        };
      }),
  );

test.describe("the app frame", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0091
  test("the account, sessions, list and send buttons share one target and one circle", async ({
    page,
  }) => {
    await settle(page);
    const found = await iconButtons(page);
    const shell = found.filter((b) =>
      ["account", "sessions-open", "menu-open", "send"].includes(b.id),
    );
    expect(shell.map((b) => b.id).sort()).toEqual(["account", "menu-open", "send", "sessions-open"]);
    expect(new Set(shell.map((b) => b.size))).toEqual(new Set(["44x44"]));
    expect(new Set(shell.map((b) => b.mark))).toEqual(new Set(["40x40"]));
  });

  // R-0091
  test("every icon button on the chat screen is a 44px target", async ({ page }) => {
    // Known defect: the cluster's info and back buttons on the picture's name
    // row are drawn smaller than the other icon buttons.
    test.fail();
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
