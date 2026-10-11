import { describe, expect, it } from "vitest";

import { monthKey, monthLabel } from "./month";

describe("month helpers", () => {
  it("addresses a month as year-month", () => {
    expect(monthKey("2026-10-01")).toBe("2026-10");
  });

  it("writes a month in French", () => {
    expect(monthLabel("2026-10-01")).toBe("octobre 2026");
    expect(monthLabel("2027-02-01")).toBe("février 2027");
  });
});
