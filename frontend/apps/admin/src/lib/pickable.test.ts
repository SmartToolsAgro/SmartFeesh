import { describe, expect, test } from "vitest";

import { pickable } from "./pickable";

const items = [
  { id: 1, name: "Chambre", is_active: true },
  { id: 2, name: "Ancienne", is_active: false },
  { id: 3, name: "Camion", is_active: true },
];

describe("pickable", () => {
  test("keeps only the active entries", () => {
    expect(pickable(items, []).map((item) => item.id)).toEqual([1, 3]);
  });

  test("keeps an archived entry that the form already points at, by id or by string", () => {
    expect(pickable(items, [2]).map((item) => item.id)).toEqual([1, 2, 3]);
    expect(pickable(items, ["2"]).map((item) => item.id)).toEqual([1, 2, 3]);
  });

  test("ignores empty choices", () => {
    expect(pickable(items, ["", null, undefined]).map((item) => item.id)).toEqual([1, 3]);
  });
});
