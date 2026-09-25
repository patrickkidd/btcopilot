import { expect, test, type Page } from "@playwright/test";
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

  // R-0185
  test("lights the moment its line names, before the words are typed", async ({
    page,
  }) => {
    await settle(page);
    // the work shows for a beat before the words land, which is the moment
    // this test is about
    await mockTurn(page, { ...added, pause: 800 });

    await page.locator("#composer").fill("She stopped calling in 1992.");
    await page.locator("#send").click();

    // the line the coach's work is reported in
    await expect(page.locator(".bub.coach .did").last()).toHaveText(/Added/);
    // and the moment it made is lit on the wire, before a word has been said.
    // The words on the picture belong to a moment the reader has picked; a
    // moment the coach has just made is its dot, lit.
    await expect(page.locator("#view circle.dot.lit")).toHaveCount(1);
    // and when the words land they name that same moment
    await expect(page.locator(".bub.coach .chip").last()).toHaveText("that winter");
  });
});

/** A turn that added someone. The board draws people, so the figure the line
 * made lights on it. */
const met = {
  statement: "I put that down.",
  statement_id: 9202,
  did: [
    { type: "tool_call", name: "edit_person", args: { name: "Ada" }, names: { it: "Ada" } },
    {
      type: "record_patch",
      turn_id: "t2",
      deltas: [
        { item_kind: "person", item_id: "1", field: "name", before: null, after: "Ada" },
      ],
    },
  ],
};

test.describe("someone the coach has just put in the record", () => {
  test.use({ storageState: stateFor("moves") });

  // R-0185
  test("lights on the board, and stays lit like a spotlit moment", async ({
    page,
  }) => {
    await settle(page);
    await mockTurn(page, met);
    // people are drawn on the board, so the board is what is on screen
    await page.locator("#cap-play").click();
    await expect(page.locator("#view .ss.board")).toBeVisible();
    await page.waitForTimeout(800);

    await page.locator("#composer").fill("My mum is Ada.");
    await page.locator("#send").click();

    await expect(page.locator('.node.lit[data-person="1"]')).toBeVisible();
    // no clock takes it away: it holds until the next thing is aimed at
    await page.waitForTimeout(3200);
    await expect(page.locator('.node.lit[data-person="1"]')).toBeVisible();
  });
});
