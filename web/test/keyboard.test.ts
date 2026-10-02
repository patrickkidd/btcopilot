import { expect, it } from "vitest";
import { Return, returnKey } from "../src/keyboard";

const press = (key: string, shift = false, alt = false, composing = false) => ({
  key,
  shiftKey: shift,
  altKey: alt,
  isComposing: composing,
});

// R-0610
it("Return sends with a real keyboard and only makes a new line on a touch screen", () => {
  expect(returnKey(press("Enter"), false)).toBe(Return.Send);
  expect(returnKey(press("Enter", true), false)).toBe(Return.Newline);
  expect(returnKey(press("Enter", false, true), false)).toBe(Return.Newline);
  expect(returnKey(press("Enter", false, false, true), false)).toBeNull();
  expect(returnKey(press("a"), false)).toBeNull();
  expect(returnKey(press("Enter"), true)).toBe(Return.Newline);
  expect(returnKey(press("Enter", true), true)).toBe(Return.Newline);
});
