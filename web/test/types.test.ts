import { describe, expect, it } from "vitest";
import { ViewKind } from "../src/types";

describe("the views the coach can put up", () => {
  // R-0286
  it.fails("no longer include two events set side by side as boxes of words", () => {
    expect(Object.values(ViewKind)).not.toContain("compare");
  });
});
