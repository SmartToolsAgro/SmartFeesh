import { describe, expect, test } from "vitest";

import { type StockByPlace, placesOf } from "./placeStock";

const byPlace: StockByPlace = new Map([
  [1, new Map([["10", "20.500"]])],
  [
    2,
    new Map([
      ["10", "100.000"],
      ["11", "0.000"],
    ]),
  ],
  [3, new Map([["11", "-2.000"]])],
]);
const names = new Map([
  [1, "Frigo 1"],
  [2, "Frigo 2"],
  [3, "Camion 3"],
]);

describe("placesOf", () => {
  test("lists the places holding a product, fullest first, with their kilos", () => {
    expect(placesOf(byPlace, names).get("10")).toEqual([
      { place: "Frigo 2", kg: "100.000" },
      { place: "Frigo 1", kg: "20.500" },
    ]);
  });

  test("leaves out the places holding nothing or less, and a product with nothing kept anywhere", () => {
    expect(placesOf(byPlace, names).has("11")).toBe(false);
  });

  test("names a place it does not know by an empty name rather than dropping its kilos", () => {
    expect(placesOf(new Map([[9, new Map([["10", "1.000"]])]]), names).get("10")).toEqual([{ place: "", kg: "1.000" }]);
  });
});
