import { describe, expect, it } from "vitest";
import { aimedEvents, chips, itemKind, token, tokenize } from "../src/chips";
import { ChipKind, ChipTone, ItemKind } from "../src/types";

const chapters = [
  { id: "ch0", cluster_ids: ["c-mid90s"], event_ids: [11, 12, 13] },
  { id: "ch1", cluster_ids: [], event_ids: [20] },
];

describe("tokenize", () => {
  it("keeps the words around a labelled chip", () => {
    const pieces = tokenize("It starts when [[event:11|Dad moved out]], then.");
    expect(pieces).toEqual([
      { text: "It starts when " },
      {
        chip: {
          kind: ChipKind.Event,
          target: "11",
          label: "Dad moved out",
          tone: ChipTone.Data,
        },
      },
      { text: ", then." },
    ]);
  });

  it("gives a bare chip a plain word rather than showing markup", () => {
    const [piece] = tokenize("[[cluster:c-mid90s]]");
    expect(piece).toEqual({
      chip: {
        kind: ChipKind.Cluster,
        target: "c-mid90s",
        label: "this stretch",
        tone: ChipTone.Data,
      },
    });
  });

  it("tones every chip in an offered message amber", () => {
    const pieces = tokenize("[[person:4|your mother]]", ChipTone.Ask);
    expect(pieces[0]).toMatchObject({ chip: { tone: ChipTone.Ask } });
  });

  it("leaves text with no markup alone", () => {
    expect(tokenize("no chips here")).toEqual([{ text: "no chips here" }]);
  });

  it("does not treat an unknown kind as a chip", () => {
    expect(tokenize("[[thing:9|x]]")).toEqual([{ text: "[[thing:9|x]]" }]);
  });

  it("narrows the coach's wider markup to the three kinds a chip may name", () => {
    expect(chips("[[events:11,13|both]]")[0].kind).toBe(ChipKind.Event);
    expect(chips("[[chapter:ch1|then]]")[0].kind).toBe(ChipKind.Cluster);
    expect(chips("[[person:4|her]]")[0].kind).toBe(ChipKind.Person);
  });

  it("keeps a span of time as plain words, not a chip that goes nowhere", () => {
    expect(tokenize("between [[range:1990-01-01..1999-12-31|the nineties]]")).toEqual([
      { text: "between " },
      { text: "the nineties" },
    ]);
  });

  it("finds every chip in a play-by-play", () => {
    const found = chips(
      "[[event:11|one]] then [[event:12|two]] and [[event:13|three]]",
    );
    expect(found.map((c) => c.target)).toEqual(["11", "12", "13"]);
  });

  it("round-trips the token it writes", () => {
    expect(chips(token(ChipKind.Cluster, "c-mid90s"))[0].target).toBe("c-mid90s");
  });
});

describe("aimedEvents", () => {
  it("aims an event chip at that event", () => {
    expect(aimedEvents(chips("[[event:12|x]]")[0], chapters)).toEqual([12]);
  });

  it("aims a multi-event chip at all of them", () => {
    expect(aimedEvents(chips("[[events:11,13|x]]")[0], chapters)).toEqual([11, 13]);
  });

  it("maps every chip kind to the item kind the record stores", () => {
    expect(itemKind(ChipKind.Event)).toBe(ItemKind.Event);
    expect(itemKind(ChipKind.Cluster)).toBe(ItemKind.Cluster);
    expect(itemKind(ChipKind.Person)).toBe(ItemKind.Person);
  });

  it("aims a cluster chip at the whole cluster, by cluster id or chapter id", () => {
    expect(aimedEvents(chips("[[cluster:c-mid90s]]")[0], chapters)).toEqual([
      11, 12, 13,
    ]);
    expect(aimedEvents(chips("[[chapter:ch1]]")[0], chapters)).toEqual([20]);
  });

  it("aims nothing when the chip names something the picture has not got", () => {
    expect(aimedEvents(chips("[[cluster:gone]]")[0], chapters)).toEqual([]);
    expect(aimedEvents(chips("[[person:4]]")[0], chapters)).toEqual([]);
  });
});
