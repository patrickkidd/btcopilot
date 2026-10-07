import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";
import { mockTurn, SEND } from "./turn";

/** A file goes with a message as input to the case: picked with the
 * paperclip or dropped on the chat, its name a chip on the message while the
 * server reads it, and a tap on the chip shows what the coach read. The
 * server is stubbed: it takes a text file and refuses anything else. */

const READ = "Dear Ann, the move to Bluff Street was hard on your father.";
const REFUSED = "The app reads PDF, JPEG, PNG, HEIC, text and Markdown files; this file is none of those.";

const file = (name: string, mimeType: string) => ({ name, mimeType, buffer: Buffer.from("Dear Ann") });
const picker = (page: Page) => page.locator("#chat-screen input[type=file]");
const picked = (page: Page) => page.locator("#inbar .attached");

/** The send answered as the server does: the turn, and for a file it read,
 * the file's name and its words; a file it cannot read refused in its words.
 * Each answer waits for `release`, so the page can be seen while it reads. */
async function serve(page: Page): Promise<{ release: () => void; sent: () => string }> {
  await mockTurn(page, { statement: "Thank you for her letter.", statement_id: 9601 });
  // the stored messages carry the two fields the server adds, null without a
  // file, until the sandbox runs the server that adds them
  const carry = (one: unknown): unknown =>
    Array.isArray(one)
      ? one.map(carry)
      : one && typeof one === "object"
        ? Object.fromEntries([
            ...("role" in one && "turn_id" in one && !("attachment_name" in one)
              ? [["attachment_name", null], ["attachment_text", null]]
              : []),
            ...Object.entries(one).map(([k, v]) => [k, carry(v)]),
          ])
        : one;
  await page.route(/\/app\/(statements|sessions)(\/\d+)?(\?.*)?$/, async (route) =>
    route.fulfill({ json: carry(await (await route.fetch()).json()) }),
  );
  await page.route(/\/app\/$/, async (route) => {
    const html = await (await route.fetch()).text();
    await route.fulfill({
      contentType: "text/html",
      body: html.replace(/window\.BOOTSTRAP=(.*?)<\/script>/, (_, json: string) => `window.BOOTSTRAP=${JSON.stringify(carry(JSON.parse(json)))}</script>`),
    });
  });
  let open: () => void = () => undefined;
  let body = "";
  await page.route(SEND, async (route) => {
    body = route.request().postData() ?? "";
    await new Promise<void>((go) => (open = go));
    if (body.includes('filename="tool.exe"')) return route.fulfill({ status: 415, body: REFUSED });
    await route.fulfill({
      status: 202,
      json: { turn_id: "t1", discussion_id: 1, statement_id: 9600, attachment_name: "letter.md", attachment_text: READ },
    });
  });
  return { release: () => open(), sent: () => body };
}

test.use({ storageState: stateFor("moves") });

// R-0713
test("a file picked or dropped goes with the message, reads, and shows what the coach read; one refused is said in a toast", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const server = await serve(page);
  await page.addInitScript(() => localStorage.setItem("fd-home-screen-asked", String(Date.now())));
  await page.goto("/app/");
  await expect(page.locator(".bub").last()).toBeVisible();

  // picked, then taken out again with its cross
  await picker(page).setInputFiles(file("notes.pdf", "application/pdf"));
  await expect(picked(page).locator(".chip")).toHaveText("notes.pdf");
  await picked(page).locator(".cardx").click();
  await expect(picked(page)).toBeHidden();

  // dropped on the chat on a computer
  await page.locator("#chat").evaluate((chat) => {
    const drag = new DataTransfer();
    drag.items.add(new File(["Dear Ann"], "letter.md", { type: "text/markdown" }));
    chat.dispatchEvent(new DragEvent("dragover", { dataTransfer: drag, bubbles: true, cancelable: true }));
    chat.dispatchEvent(new DragEvent("drop", { dataTransfer: drag, bubbles: true, cancelable: true }));
  });
  await expect(picked(page).locator(".chip")).toHaveText("letter.md");

  // sent: the name is on the message, still, while the server reads it
  await page.locator("#composer").fill("Here is her letter");
  await page.locator("#send").click();
  await expect(picked(page)).toBeHidden();
  const chip = page.locator(".bub.user").last().locator(".file .chip");
  await expect(chip).toHaveClass(/reading/);
  await expect(chip).toBeDisabled();
  expect(server.sent()).toContain('name="file"; filename="letter.md"');
  expect(server.sent()).toContain("Here is her letter");
  server.release();

  // read: a tap shows what the coach read, and the cross puts it away
  await expect(chip).not.toHaveClass(/reading/);
  await chip.click();
  const sheet = page.locator(".fs-sheet.fl");
  await expect(sheet).toContainText(READ);
  await expect(sheet.locator(".cf-t")).toHaveText("letter.md");
  const inside = await sheet.evaluate((s) => {
    const box = s.getBoundingClientRect();
    return [...s.querySelectorAll("*")].every((n) => {
      const r = n.getBoundingClientRect();
      return r.width === 0 || (r.left >= box.left - 1 && r.right <= box.right + 1);
    });
  });
  expect(inside).toBe(true);
  await sheet.locator(".cardx").click();
  await expect(sheet).not.toHaveClass(/\bin\b/);
  await expect(page.locator(".bub.coach").last()).toContainText("Thank you for her letter.");

  // refused: the server's words in a toast, the message back in the box
  await picker(page).setInputFiles(file("tool.exe", "application/octet-stream"));
  await page.locator("#composer").fill("And this one");
  const users = await page.locator(".bub.user").count();
  await page.locator("#send").click();
  server.release();
  await expect(page.locator(".toast")).toHaveText(REFUSED);
  // it stays long enough to read, past the 1.5 s of every other toast
  await page.waitForTimeout(3000);
  await expect(page.locator(".toast")).toHaveCount(1);
  await expect(page.locator("#composer")).toHaveText("And this one");
  await expect(page.locator(".bub.user")).toHaveCount(users);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
