import { describe, expect, it } from "vitest";

import { formatRate, typed } from "./shared";

describe("formatRate", () => {
  it("drops the zeros the server adds and uses a decimal comma", () => {
    expect(formatRate("40.00")).toBe("40");
    expect(formatRate("25.50")).toBe("25,5");
    expect(formatRate("12.75")).toBe("12,75");
    expect(formatRate("0.00")).toBe("0");
    expect(formatRate("100.00")).toBe("100");
  });
});

describe("typed", () => {
  it("puts an amount back as a person types it", () => {
    expect(typed("1500.000")).toBe("1500,000");
  });
});
