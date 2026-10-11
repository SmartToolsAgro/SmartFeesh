import { expect, test } from "vitest";

import { fromThousandths, lineTotal, marginPercent, percentChange, percentOf, subtract, sum, toThousandths } from "./decimal";

test("a discount in percent is rounded once to the millime, like the server", () => {
  // 94.568 × 7.5 % = 7.0926 → 7.093
  expect(percentOf("94.568", "7.5")).toBe("7.093");
  expect(percentOf("210", "10")).toBe("21.000");
  expect(percentOf("210", "0")).toBe("0.000");
});

test("decimal strings become thousandths and back, exactly", () => {
  expect(toThousandths("20.25")).toBe(20250n);
  expect(toThousandths("-0.5")).toBe(-500n);
  expect(fromThousandths(20250n)).toBe("20.250");
  expect(fromThousandths(-5n)).toBe("-0.005");
  expect(() => toThousandths("1.2345")).toThrow(TypeError);
  expect(() => toThousandths("20,5")).toThrow(TypeError);
});

test("a line total is rounded once, half up, like the server", () => {
  expect(lineTotal("62", "20.255")).toBe("1255.810");
  // 2.345 kg at 42.500 DT = 99.6625 → 99.663
  expect(lineTotal("2.345", "42.500")).toBe("99.663");
});

test("sums and differences are exact", () => {
  expect(sum(["0.1", "0.2"])).toBe("0.300");
  expect(sum([])).toBe("0.000");
  expect(subtract("60", "62")).toBe("-2.000");
});

test("the change against the last cost, in percent with one decimal", () => {
  expect(percentChange("20.250", "20")).toBe("1.3");
  expect(percentChange("18", "20")).toBe("-10.0");
  expect(percentChange("20", "20")).toBe("0.0");
  expect(percentChange("5", "0")).toBeNull();
});

test("the margin percentage is taken on the price, one decimal", () => {
  expect(marginPercent("30.000", "23.000")).toBe("23.3");
  expect(marginPercent("10.000", "12.500")).toBe("-25.0");
  expect(marginPercent("0.000", "5.000")).toBeNull();
});
