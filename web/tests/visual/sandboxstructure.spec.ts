import { test } from "./fixtures";
import { need, sandboxOnly, walker } from "./sandbox";
import { addForm, readOnly } from "./setup";

// A walk of the three screens people and family structure reach: the person
// editor, the ballot with a person on it, and the meeting with the same person.

test.describe(() => {
  sandboxOnly("editor", "coder", "table");
  test.describe.configure({ timeout: 600_000 });

  // R-0326, R-0887
  test("people and family structure: the editor, the ballot and the meeting", async ({ page }, info) => {
    const { say, check, shot, text, visible, gates, changed, quiet } = walker(
      page,
      info,
    );
    const editorInvite = need("editor");
    const coderInvite = need("coder");
    const adminInvite = need("table");


    // ── 1. the person editor: what it shows, read only ────────────────────
    // The forms are read only (R-0887): people, their parents and their bonds
    // are changed through the coach, so the walk only reads the form.
    await page.goto(editorInvite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await page.locator(".caption .listglyph").first().click();
    await page.waitForTimeout(900);
    await page.locator("#tab-people").click();
    await page.waitForTimeout(700);
    await addForm(page, "person");
    await page.waitForTimeout(700);
    const labels = await page.locator(".editor .lab").allInnerTexts();
    say(`editor fields: ${JSON.stringify(labels)}`);
    const said = labels.map((one) => one.trim().toLowerCase());
    check(said.includes("born to"), "the person editor asks who they were born to");
    check(said.includes("bonds"), "the person editor lists the bonds they are in");
    await readOnly(page.locator("#add-sheet .editor"));
    await gates("the person editor");
    await shot("1-person-editor");

    // ── 2. the ballot with a person on it ─────────────────────────────────
    await page.goto(coderInvite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1600);
    await page.locator(".tkcard .addbtn").first().click();
    await page.waitForTimeout(1800);
    check(await visible("#ballot-screen"), "the vote opens as its own screen");
    let found = false;
    for (let i = 0; i < 14 && !found; i += 1) {
      found = /a person|a couple/.test(await text("#ballot-body .progress"));
      if (!found) {
        await page.locator("#bl-next").click();
        await page.waitForTimeout(700);
      }
    }
    check(found, "a person or a couple is one of the items on the ballot");
    const versions = await page.locator("#ballot-body .opinion").count();
    const drawn = await page.locator("#ballot-body .opinion svg.fragment").count();
    say(
      `item="${await text("#ballot-body h3")}" versions=${versions} drawn=${drawn}`,
    );
    check(versions >= 2, `the versions are shown (${versions})`);
    check(drawn === versions, `each version is drawn as a family (${drawn})`);
    await gates("the ballot with a person on it");
    await shot("3-ballot-person");

    await page.locator("#bl-change").click();
    await page.waitForTimeout(900);
    check(
      await visible(".bl-sheet .editor"),
      "change opens the person's own editor as a sheet",
    );
    // the vote stays, but the form's parents and bond pickers write to the
    // diagram itself, so they are shut (R-0887)
    check(
      (await page.locator(".bl-sheet .parents:not([disabled]), .bl-sheet .bondrow:not([disabled])").count()) === 0,
      "the person editor over the ballot offers no parents or bond pickers to use",
    );
    await gates("the person editor over the ballot");
    await shot("4-ballot-editor");
    await page.locator(".bl-sheet .acts .del").click();
    await page.waitForTimeout(800);

    // ── 3. the meeting with the same person ───────────────────────────────
    await page.goto(adminInvite, { waitUntil: "networkidle" });
    await page.waitForTimeout(1800);
    await page.locator("#account").click();
    await page.waitForTimeout(900);
    await page.locator(".sn-pane.in .sn-row", { hasText: "Next meeting" }).click();
    await page.waitForTimeout(1600);
    await page.locator(".tb-meet").first().click();
    await page.locator(".tb-run").first().click();
    await page.waitForTimeout(2200);
    check(await visible("#meeting-screen"), "the meeting opens");
    const key = await text("#meeting-stats .mkey");
    const rowNames = await page.locator("#meeting-body .pick, #meeting-body .collapsed span").allInnerTexts();
    const shapes = await page.locator("#meeting-body svg.fragment").count();
    say(`legend="${key.replace(/\n/g, " ")}" shapes=${shapes}`);
    check(/people/.test(key) && /bonds?/.test(key), "the legend counts the family");
    check(
      (await page.locator("#meeting-view circle").count()) > 0,
      "the wire still draws the events",
    );
    check(
      rowNames.some((one) => /Corinne/.test(one)),
      `the person is a row in the list (${rowNames.slice(0, 4).join(" | ")})`,
    );
    check(shapes > 0, `a version of the person is drawn in the room (${shapes})`);
    await gates("the meeting with a person on it");
    await shot("5-meeting-person");


    await quiet();
  });
});
