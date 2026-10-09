import { expect, test, type Page } from "./fixtures";
import { stateFor } from "./setup";
import { mockTurn } from "./turn";

/** What the coach did, said one line at a time, lights the thing it put in the
 * record as its line lands. A moment lights as its dot on the wire; a person
 * lights wherever people are drawn, which today is the board. */

const settle = async (page: Page) => {
  await page.goto("/app/");
  await expect(page.locator("#view .ss")).toBeVisible();
  await page.waitForTimeout(500);
};

/** A turn that added one moment, told the way the server tells it: the call,
 * then the patch naming what it made. Event 22 is on the moves record. */
const added = {
  statement: "I put that down. [[event:22|that winter]]",
  statement_id: 9201,
  did: [
    {
      type: "tool_call",
      name: "edit_event",
      args: {
        description: "she stopped calling",
        dateTime: "1992-04-01",
        dateCertainty: "certain",
      },
      // the server names what a call touches before it runs
      names: { it: "she stopped calling" },
    },
    {
      type: "record_patch",
      turn_id: "t1",
      deltas: [
        {
          item_kind: "event",
          item_id: "22",
          field: "description",
          before: null,
          after: "she stopped calling",
        },
      ],
    },
  ],
};

test.describe("what the coach did, one line at a time", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0185, R-0544
  test("lights the moment its line names, before the words are typed", async ({
    page,
  }) => {
    await settle(page);
    // the work shows for a beat before the words land, which is the moment
    // this test is about
    await mockTurn(page, { ...added, pause: 800 });
    await expect(page.locator("#view rect.pill.add, #view rect.pill.change")).toHaveCount(0);

    await page.locator("#composer").fill("She stopped calling in 1992.");
    await page.locator("#send").click();

    // the line the coach's work is reported in
    await expect(page.locator(".bub.coach .did").last()).toHaveText(/Added/);
    // and the moment it made is lit on the wire, before a word has been said.
    // The words on the picture belong to a moment the reader has picked; a
    // moment the coach has just written inside a cluster takes its colour on
    // that cluster's pill.
    await expect(page.locator("#view rect.pill.add, #view rect.pill.change")).toHaveCount(1);
    // and when the words land they name that same moment
    await expect(page.locator(".bub.coach .chip").last()).toHaveText("that winter");
  });
});

