import { describe, expect, it } from "vitest";
import { lookOrder } from "../src/pairings";
import { Confidence, ItemKind, ItemStatus, type BallotItem } from "../src/types";

const item = (
  id: number,
  kind: ItemKind,
  confidence: Confidence | null,
  dateTime = "2000-01-01",
): BallotItem =>
  ({
    id,
    item_kind: kind,
    status: ItemStatus.Disputed,
    pairing_confidence: confidence,
    opinions: [{ coding_id: 1, item_id: id, item: { dateTime } }],
  }) as unknown as BallotItem;

describe("Patrick's look over the pairings", () => {
  // R-0963
  it("puts the unsure ones first, then likely, then sure, each in the order the ballot walks", () => {
    const items = [
      item(1, ItemKind.Event, Confidence.Sure, "1990-01-01"),
      item(2, ItemKind.Event, Confidence.Unsure, "2001-01-01"),
      item(3, ItemKind.Event, Confidence.Likely),
      item(4, ItemKind.Person, Confidence.Sure),
      item(5, ItemKind.Event, Confidence.Unsure, "1999-01-01"),
    ];
    expect(lookOrder(items).map((one) => one.id)).toEqual([5, 2, 3, 4, 1]);
  });

  // R-0963
  it("leaves out a row no coder wrote anything in", () => {
    const empty = { ...item(6, ItemKind.Event, Confidence.Unsure), opinions: [] };
    expect(lookOrder([empty, item(7, ItemKind.Event, Confidence.Sure)]).map((one) => one.id)).toEqual([7]);
  });
});
