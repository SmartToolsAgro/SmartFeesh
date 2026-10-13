import type { BoxBalance } from "@frutti/api";
import { describe, expect, test } from "vitest";

import { customerBoxCounts, formatBoxCount, holdersFromBalances, holdersOfKind } from "./shared";

function row(holder_id: number, holder_kind: string, holder_name: string, box_type: "small" | "big", count: number) {
  return { holder_id, holder_kind, holder_name, box_type, count } as BoxBalance;
}

describe("holdersFromBalances", () => {
  test("puts both box types of a holder on one row and counts a missing type as 0", () => {
    const holders = holdersFromBalances([
      row(1, "location", "Camion 1", "small", 12),
      row(2, "customer", "Hôtel", "big", 4),
    ]);

    expect(holders).toEqual([
      { id: 1, name: "Camion 1", kind: "location", small: 12, big: 0 },
      { id: 2, name: "Hôtel", kind: "customer", small: 0, big: 4 },
    ]);
  });

  test("keeps a holder whose count is 0 as 0", () => {
    const holders = holdersFromBalances([row(3, "supplier", "Fournisseur A", "small", 0)]);

    expect(holders).toEqual([{ id: 3, name: "Fournisseur A", kind: "supplier", small: 0, big: 0 }]);
  });

  test("skips rows of an unknown holder kind", () => {
    expect(holdersFromBalances([row(4, "truck", "?", "small", 9)])).toEqual([]);
  });

  test("sorts by name within the list", () => {
    const holders = holdersFromBalances([
      row(1, "customer", "Zeta", "small", 1),
      row(2, "customer", "Alpha", "small", 1),
    ]);

    expect(holders.map((holder) => holder.name)).toEqual(["Alpha", "Zeta"]);
  });

  test("holdersOfKind keeps one kind", () => {
    const holders = holdersFromBalances([
      row(1, "location", "Froid", "small", 2),
      row(2, "supplier", "Fournisseur", "big", 5),
    ]);

    expect(holdersOfKind(holders, "supplier").map((holder) => holder.id)).toEqual([2]);
  });
});

describe("customerBoxCounts", () => {
  test("reads the client's holder by name and client kind only", () => {
    const holders = holdersFromBalances([
      row(1, "customer", "Hôtel Sfax", "small", 7),
      row(2, "supplier", "Hôtel Sfax", "small", 99),
    ]);

    expect(customerBoxCounts(holders, "Hôtel Sfax")).toEqual({ small: 7, big: 0, ambiguous: false });
  });

  test("a client with no holder row holds 0 boxes", () => {
    expect(customerBoxCounts([], "Nouveau client")).toEqual({ small: 0, big: 0, ambiguous: false });
  });

  test("two client holders with the same name are flagged as ambiguous", () => {
    const holders = holdersFromBalances([
      row(1, "customer", "Doublon", "small", 1),
      row(2, "customer", "Doublon", "big", 2),
    ]);

    expect(customerBoxCounts(holders, "Doublon").ambiguous).toBe(true);
  });
});

describe("formatBoxCount", () => {
  test("formats an integer without decimals or unit", () => {
    expect(formatBoxCount(1250, "fr")).toMatch(/^1\s?250$/);
    expect(formatBoxCount(0, "fr")).toBe("0");
  });

  test("rejects a value that is not an integer", () => {
    expect(() => formatBoxCount(1.5, "fr")).toThrow(TypeError);
  });
});
