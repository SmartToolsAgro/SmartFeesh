import { describe, expect, it } from "vitest";

import { dueDateOf, shapeOf } from "./shared";

describe("dueDateOf", () => {
  it("is the day itself when paid at once", () => {
    expect(dueDateOf("2026-10-15", "cash", 0)).toBe("2026-10-15");
  });

  it("counts N calendar days", () => {
    expect(dueDateOf("2026-10-15", "days", 30)).toBe("2026-11-14");
  });

  it("is the end of the month, plus N days", () => {
    expect(dueDateOf("2026-10-15", "month_end", 0)).toBe("2026-10-31");
    expect(dueDateOf("2028-02-03", "month_end", 0)).toBe("2028-02-29");
    expect(dueDateOf("2026-12-31", "month_end", 10)).toBe("2027-01-10");
  });
});

describe("shapeOf", () => {
  it("reads a field of the purchase", () => {
    expect(shapeOf({ field: "boxes.small", line: null, before: null, after: "3" })).toEqual({
      kind: "header",
      field: "boxes.small",
    });
  });

  it("reads a field of a line, numbered from 1", () => {
    expect(shapeOf({ field: "lines.received_quantity", line: 0, before: null, after: "48.000" })).toEqual({
      kind: "row",
      row: "line",
      number: 1,
      field: "received_quantity",
    });
  });

  it("reads a payment added", () => {
    expect(shapeOf({ field: "payments.added", line: 1, before: null, after: "500.000" })).toEqual({
      kind: "added",
      row: "payment",
      number: 2,
    });
  });
});
