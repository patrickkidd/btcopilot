import { describe, expect, it } from "vitest";
import { MAX_FIELD_LINES, grownHeight } from "../src/editor";

describe("grownHeight", () => {
  // R-0458
  it("takes the text's own height until ten lines, then stays", () => {
    const line = 22;
    const pad = 22;
    expect(grownHeight(line * 3 + pad, line, pad)).toBe(line * 3 + pad);
    expect(grownHeight(line * 40 + pad, line, pad)).toBe(
      line * MAX_FIELD_LINES + pad,
    );
  });
});
