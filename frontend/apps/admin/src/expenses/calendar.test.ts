import { expect, test } from "vitest";

import { addMonths, daysIn, monthBounds, monthOf, weeksOf } from "./calendar";

test("months move across years", () => {
  expect(addMonths({ year: 2026, month: 12 }, 1)).toEqual({ year: 2027, month: 1 });
  expect(addMonths({ year: 2026, month: 1 }, -1)).toEqual({ year: 2025, month: 12 });
  expect(monthOf("2026-10-11")).toEqual({ year: 2026, month: 10 });
});

test("a month knows its days, leap years included", () => {
  expect(daysIn({ year: 2028, month: 2 })).toBe(29);
  expect(monthBounds({ year: 2026, month: 10 })).toEqual({ first: "2026-10-01", last: "2026-10-31" });
});

test("weeks start on Monday and pad the month with empty cells", () => {
  // 1 October 2026 is a Thursday.
  const weeks = weeksOf({ year: 2026, month: 10 });
  expect(weeks[0]).toEqual([null, null, null, "2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]);
  expect(weeks.every((week) => week.length === 7)).toBe(true);
  expect(weeks.flat().filter(Boolean)).toHaveLength(31);
  expect(weeks).toHaveLength(5);
  expect(weeks.at(-1)?.at(-1)).toBeNull();
});
