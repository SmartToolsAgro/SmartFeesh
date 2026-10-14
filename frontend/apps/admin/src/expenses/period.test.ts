import { expect, test } from "vitest";

import { asMonth, asPeriod, openingPeriod, periodDates } from "./period";

const THIS_MONTH = "2026-10-01";

test("the list opens on this month", () => {
  expect(openingPeriod(null, null, THIS_MONTH)).toEqual({ mode: "month", month: "2026-10-01" });
});

test("a link to a whole month opens on that month", () => {
  expect(openingPeriod("2026-09-01", "2026-09-30", THIS_MONTH)).toEqual({ mode: "month", month: "2026-09-01" });
  expect(openingPeriod("2028-02-01", "2028-02-29", THIS_MONTH)).toEqual({ mode: "month", month: "2028-02-01" });
});

test("a link to other dates opens on that period, an absent bound left open", () => {
  expect(openingPeriod("2026-09-05", "2026-09-30", THIS_MONTH)).toEqual({
    mode: "period",
    from: "2026-09-05",
    to: "2026-09-30",
  });
  expect(openingPeriod("2026-09-01", "2026-10-31", THIS_MONTH)).toEqual({
    mode: "period",
    from: "2026-09-01",
    to: "2026-10-31",
  });
  expect(openingPeriod("2026-09-01", null, THIS_MONTH)).toEqual({ mode: "period", from: "2026-09-01", to: "" });
  expect(openingPeriod(null, "2026-09-30", THIS_MONTH)).toEqual({ mode: "period", from: "", to: "2026-09-30" });
});

test("a link with dates that are not dates opens on this month", () => {
  expect(openingPeriod("hier", "2026-13", THIS_MONTH)).toEqual({ mode: "month", month: "2026-10-01" });
});

test("a month asks the server for its first to its last day", () => {
  expect(periodDates({ mode: "month", month: "2026-10-01" })).toEqual({
    date_from: "2026-10-01",
    date_to: "2026-10-31",
  });
  expect(periodDates({ mode: "month", month: "2028-02-01" })).toEqual({
    date_from: "2028-02-01",
    date_to: "2028-02-29",
  });
});

test("a period asks for its bounds, and nothing for an open one", () => {
  expect(periodDates({ mode: "period", from: "2026-09-05", to: "2026-10-02" })).toEqual({
    date_from: "2026-09-05",
    date_to: "2026-10-02",
  });
  expect(periodDates({ mode: "period", from: "", to: "2026-10-02" })).toEqual({ date_to: "2026-10-02" });
  expect(periodDates({ mode: "period", from: "", to: "" })).toEqual({});
});

test("going from the month to a period keeps the month's dates", () => {
  expect(asPeriod({ mode: "month", month: "2026-09-01" })).toEqual({
    mode: "period",
    from: "2026-09-01",
    to: "2026-09-30",
  });
});

test("going back to the month shows the month the period starts in, else ends in, else this month", () => {
  expect(asMonth({ mode: "period", from: "2026-08-17", to: "2026-09-30" }, THIS_MONTH)).toEqual({
    mode: "month",
    month: "2026-08-01",
  });
  expect(asMonth({ mode: "period", from: "", to: "2026-09-12" }, THIS_MONTH)).toEqual({
    mode: "month",
    month: "2026-09-01",
  });
  expect(asMonth({ mode: "period", from: "", to: "" }, THIS_MONTH)).toEqual({ mode: "month", month: "2026-10-01" });
  // A date field lets a year of five digits through.
  expect(asMonth({ mode: "period", from: "12026-09-01", to: "" }, THIS_MONTH)).toEqual({
    mode: "month",
    month: "2026-10-01",
  });
});

test("a period that starts after today goes back to this month: no expense is dated in the future", () => {
  expect(asMonth({ mode: "period", from: "2027-01-10", to: "" }, THIS_MONTH)).toEqual({
    mode: "month",
    month: "2026-10-01",
  });
});
