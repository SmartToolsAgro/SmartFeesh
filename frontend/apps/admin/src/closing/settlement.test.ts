import { describe, expect, it } from "vitest";

import { remainingToPay } from "./settlement";

describe("remainingToPay", () => {
  it("is zero when the payments add up to the millime", () => {
    expect(remainingToPay("1286.000", ["1000.000", "286.000"])).toBe("0.000");
    expect(remainingToPay("0.300", ["0.100", "0.200"])).toBe("0.000");
  });

  it("is positive when short and negative when over", () => {
    expect(remainingToPay("1286.000", ["1000.000"])).toBe("286.000");
    expect(remainingToPay("100.000", ["100.001"])).toBe("-0.001");
  });

  it("ignores empty lines and refuses text or finer than a millime", () => {
    expect(remainingToPay("50.000", ["", "50.000"])).toBe("0.000");
    expect(remainingToPay("50.000", ["abc"])).toBeNull();
    expect(remainingToPay("50.000", ["50.0005"])).toBeNull();
  });
});
