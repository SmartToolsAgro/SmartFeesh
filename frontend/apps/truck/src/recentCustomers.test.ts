import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { forgetRecentCustomers, recentCustomerIds, rememberCustomer } from "./recentCustomers";

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("the customers sold to most recently come first, each once, five at most", () => {
  for (const id of [1, 2, 3, 2, 4, 5, 6]) rememberCustomer(id);
  expect(recentCustomerIds()).toEqual([6, 5, 4, 2, 3]);
});

test("a phone that refuses storage shows no recent customers and does not fail", () => {
  const refused = () => {
    throw new Error("blocked");
  };
  vi.stubGlobal("localStorage", { getItem: refused, setItem: refused, removeItem: refused });
  expect(() => rememberCustomer(1)).not.toThrow();
  expect(recentCustomerIds()).toEqual([]);
  expect(() => forgetRecentCustomers()).not.toThrow();
});

test("forgetting clears the list", () => {
  rememberCustomer(7);
  forgetRecentCustomers();
  expect(recentCustomerIds()).toEqual([]);
});
