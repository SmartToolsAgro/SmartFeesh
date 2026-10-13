import { expect, test } from "vitest";

import { boxCountsOf, formatBoxCount, hasBoxes, NO_BOXES, wholeCount } from "./boxes";

test("an empty box input means none, and only whole counts are accepted", () => {
  expect(wholeCount("")).toBe(0);
  expect(wholeCount("  ")).toBe(0);
  expect(wholeCount(" 3 ")).toBe(3);
  expect(wholeCount("0")).toBe(0);
  expect(wholeCount("2.5")).toBeNull();
  expect(wholeCount("-1")).toBeNull();
  expect(wholeCount("1e3")).toBeNull();
  expect(wholeCount("abc")).toBeNull();
  expect(wholeCount("99999999999999999999")).toBeNull();
});

test("the counts to send are null as soon as one box type is not a whole number", () => {
  expect(boxCountsOf(NO_BOXES)).toEqual({ small: 0, big: 0 });
  expect(boxCountsOf({ small: "4", big: "" })).toEqual({ small: 4, big: 0 });
  expect(boxCountsOf({ small: "4", big: "1.5" })).toBeNull();
});

test("a sale or a pickup has boxes only when one count is above zero", () => {
  expect(hasBoxes({ small: 0, big: 0 })).toBe(false);
  expect(hasBoxes({ small: 0, big: 1 })).toBe(true);
});

test("a box count is an integer without a unit, in the language asked", () => {
  expect(formatBoxCount(0, "fr")).toBe("0");
  expect(formatBoxCount(12, "fr")).toBe("12");
  expect(() => formatBoxCount(1.5, "fr")).toThrow(TypeError);
});
