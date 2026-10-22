import { describe, expect, it } from "vitest";
import { costLine, partsOf, wordCount } from "../src/longnotes";
import { feed, type TurnSink } from "../src/turn";
import { TurnEventKind } from "../src/types";

const AT = { part_words: 1500, usd_per_1000_words: 1.95, seconds_per_part: 97 };

describe("pricing notes too long for one part", () => {
  // R-0897
  it("counts what whitespace separates", () => {
    expect(wordCount("  She left\n\nhome  in 1990.\t")).toBe(5);
    expect(wordCount("")).toBe(0);
  });

  // R-0897
  it("asks only when the words need more than one part", () => {
    expect(partsOf(300, AT)).toBe(1);
    expect(partsOf(1500, AT)).toBe(1);
    expect(partsOf(1501, AT)).toBe(2);
    expect(partsOf(4000, AT)).toBe(3);
  });

  // R-0897
  it("says the words, the parts, the dollars to 5 cents and the minutes rounded up", () => {
    expect(costLine(4000, AT)).toBe("About 4,000 words in 3 parts. Roughly $7.80 and 5 minutes.");
    expect(costLine(12000, AT)).toBe("About 12,000 words in 8 parts. Roughly $23.40 and 13 minutes.");
    expect(costLine(1600, { ...AT, usd_per_1000_words: 0.11, seconds_per_part: 20 })).toBe(
      "About 1,600 words in 2 parts. Roughly $0.20 and 1 minute.",
    );
  });

  // R-0897
  it("hands on which part the coach is entering", () => {
    const parts: string[] = [];
    const take = feed({ part: (k: number, n: number) => void parts.push(`${k}/${n}`) } as unknown as TurnSink);
    take({ type: TurnEventKind.Part, part: 2, parts: 3 });
    expect(parts).toEqual(["2/3"]);
  });
});
