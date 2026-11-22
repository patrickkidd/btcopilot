import { expect, it } from "vitest";
import { because, dayOf, guessed, namedFor, Who, type Choice } from "../src/recording";

// R-0953
it("dates a recording by the person's own calendar day, not the day in UTC", () => {
  const zone = process.env.TZ;
  process.env.TZ = "America/Anchorage";
  // 15:31 on 21 November in Alaska is already 22 November in UTC
  expect(dayOf(new File(["a"], "x.m4a", { lastModified: Date.UTC(2026, 10, 22, 0, 31) }))).toBe("2026-11-21");
  process.env.TZ = zone;
});

// R-0951
it("says whose words a suggestion rests on only when another speaker said them", () => {
  const voice = { label: "B", said: "Corinne, you were too little to remember", suggestion: null };
  expect(because(voice, { person_id: 5, because: "Thank you, Corinne", speaker: "A" })).toContain("Speaker A said: <q>Thank you, Corinne</q>");
  expect(because(voice, { person_id: 5, because: "Corinne, you were too little", speaker: "B" })).toBe("");
  const alone = because(voice, { person_id: 5, because: "My name is Corinne", speaker: "B" });
  expect(alone).toContain("<q>My name is Corinne</q>");
  expect(alone).not.toContain("said:");
});

// R-0951
it("tells the server each speaker's person, a new person by the id made for them on Save", () => {
  const chosen = new Map<string, Choice>([
    ["A", { who: Who.Person, id: 5 }],
    ["B", { who: Who.New, name: "Gerald", last: "Whitlock" }],
  ]);
  expect(namedFor(chosen, new Map([["B", 91]]))).toEqual({ A: { person_id: 5 }, B: { person_id: 91 } });
});

// R-0951
it("fills each speaker with the app's suggestion, a person in the diagram or the clinician", () => {
  expect(guessed({ person_id: 5, because: "Corinne, you were too little", speaker: "B" })).toEqual({ who: Who.Person, id: 5 });
  expect(guessed({ person_id: null, because: "Thank you both for coming in", speaker: "A" })).toEqual({ who: Who.Clinician });
});

// R-0952
it("takes a recording with no clinician in it, or any mix of speakers", () => {
  const none = new Map<string, Choice>([
    ["A", { who: Who.Person, id: 5 }],
    ["B", { who: Who.Outside, name: "Aunt Rosalie" }],
  ]);
  expect(namedFor(none, new Map())).toEqual({ A: { person_id: 5 }, B: { name: "Aunt Rosalie" } });
  const one = new Map<string, Choice>([["A", { who: Who.Clinician }]]);
  expect(namedFor(one, new Map())).toEqual({ A: { clinician: true } });
});

// R-0953
it("dates a recording by the day its file was made", () => {
  expect(dayOf(new File(["a"], "x.m4a", { lastModified: Date.UTC(2026, 10, 2, 15) }))).toBe("2026-11-02");
});
