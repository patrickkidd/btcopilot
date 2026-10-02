import { expect, test, type Page } from "@playwright/test";
import { openList, stateFor } from "./setup";

/** Words with no place to break, longer than any phone is wide. */
const LONG = "Fitzgerald-Winterbottom".repeat(10);

/** Every box in the editor that reaches past its parent's left or right edge,
 * and how far the list, the caption and the page can be scrolled sideways. */
const spill = (page: Page) =>
  page.evaluate(() => {
    const editor = document.querySelector(".editor")!;
    const outside = [editor, ...editor.querySelectorAll("*")].flatMap((node) => {
      const a = node.getBoundingClientRect();
      const b = node.parentElement!.getBoundingClientRect();
      return a.width && (a.left < b.left - 1 || a.right > b.right + 1)
        ? [`${node.tagName}.${node.className} ${Math.round(a.right - b.right)}px`]
        : [];
    });
    const list = document.getElementById("menu-body")!;
    // the row of chips over the picture, and how far its list button reaches
    // into the row's end padding, which Safari counts again past the button
    const caption = document.getElementById("caption")!;
    const end =
      caption.getBoundingClientRect().right - parseFloat(getComputedStyle(caption).paddingRight);
    const button = caption.querySelector(".listglyph")!.getBoundingClientRect();
    return {
      outside,
      page: document.scrollingElement!.scrollWidth - innerWidth,
      list: list.scrollWidth - list.clientWidth,
      caption: caption.scrollWidth - caption.clientWidth,
      reach: Math.max(0, Math.round(button.right - end)),
    };
  });

for (const width of [320, 390])
  test.describe(`the event editor at ${width} wide`, () => {
    test.use({ storageState: stateFor("hostile"), viewport: { width, height: 844 } });

    // R-0174, R-0104, R-0069
    test("lays out in one column and never scrolls sideways", async ({ page }) => {
      test.skip(test.info().project.name !== "phone");
      await page.goto("/app/");
      await openList(page);
      // the form is reached only to add an event while it is parked (PARKED)
      await page.locator("#menu-add").click();
      const editor = page.locator(".editor");
      await expect(editor.locator(".segs").first()).toBeVisible();
      await editor.locator('[data-name="description"]').fill(LONG);
      await editor.locator('[data-name="location"]').fill(LONG);
      await editor.locator('[data-name="endDateTime"]').fill("2003-04-05");
      expect(await spill(page)).toEqual({ outside: [], page: 0, list: 0, caption: 0, reach: 0 });
      // Safari on iPhone sizes a date field with its native look content-box,
      // padding and border outside the width, whatever the page asks for.
      const looks = await editor
        .locator(".f")
        .evaluateAll((fields) => fields.map((f) => getComputedStyle(f).appearance));
      expect(new Set(looks)).toEqual(new Set(["none"]));
    });
  });
