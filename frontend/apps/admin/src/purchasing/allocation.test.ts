import { describe, expect, it } from "vitest";

import { compare, spread } from "./allocation";
import { addDays } from "./shared";

describe("spread", () => {
  it("pays the oldest invoices first, in full, then part of the next", () => {
    expect(spread("1500", ["1255.500", "100.000", "300.000"])).toEqual(["1255.500", "100.000", "144.500"]);
  });

  it("leaves the rest as an advance when the invoices are all paid", () => {
    expect(spread("2000.000", ["1255.500", "100"])).toEqual(["1255.500", "100.000"]);
  });

  it("gives nothing once the amount runs out", () => {
    expect(spread("0.001", ["1", "1"])).toEqual(["0.001", ""]);
    expect(spread("0", ["1"])).toEqual([""]);
  });
});

describe("compare", () => {
  it("compares decimals exactly", () => {
    expect(compare("0.1", "0.100")).toBe(0);
    expect(compare("1255.499", "1255.5")).toBe(-1);
    expect(compare("10", "9.999")).toBe(1);
  });
});

describe("addDays", () => {
  it("moves on calendar dates across months and years", () => {
    expect(addDays("2026-10-11", 30)).toBe("2026-11-10");
    expect(addDays("2026-12-15", 30)).toBe("2027-01-14");
    expect(addDays("not a date", 30)).toBe("not a date");
  });
});
