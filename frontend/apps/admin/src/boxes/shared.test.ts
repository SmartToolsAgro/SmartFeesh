import type { BoxBalance } from "@frutti/api";
import { describe, expect, test } from "vitest";

import {
  boxCountsFromInputs,
  boxInputsFromCounts,
  boxSummary,
  customerBoxCounts,
  formatBoxCount,
  holdersFromBalances,
  holdersOfKind,
  NO_BOX_INPUTS,
} from "./shared";

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

describe("boxSummary", () => {
  test("own boxes = in hand + at clients − owed to suppliers, per box type", () => {
    // The owner's screen of 2026-10-18: 50 small and 50 big of the company's own.
    const holders = holdersFromBalances([
      row(1, "location", "Chambre froide 1", "small", 39),
      row(1, "location", "Chambre froide 1", "big", 55),
      row(2, "location", "ISUZI 2", "big", 15),
      row(3, "customer", "Marée du Sud", "small", 10),
      row(3, "customer", "Marée du Sud", "big", 12),
      row(4, "customer", "Poissonnerie El Bahr", "big", 10),
      row(5, "customer", "Restaurant Le Corail", "small", 2),
      row(5, "customer", "Restaurant Le Corail", "big", 18),
      row(6, "supplier", "Mareyeur Port de Sfax", "small", 1),
      row(6, "supplier", "Mareyeur Port de Sfax", "big", 10),
      row(7, "supplier", "Surgelés du Sahel", "big", 50),
    ]);

    expect(boxSummary(holders)).toEqual({
      small: { inHand: 39, atCustomers: 12, owedToSuppliers: 1, own: 50 },
      big: { inHand: 70, atCustomers: 40, owedToSuppliers: 60, own: 50 },
    });
  });

  test("no holders: every figure is 0", () => {
    const empty = { inHand: 0, atCustomers: 0, owedToSuppliers: 0, own: 0 };
    expect(boxSummary([])).toEqual({ small: empty, big: empty });
  });

  test("own goes below 0 when more boxes are owed than we have", () => {
    const holders = holdersFromBalances([
      row(1, "location", "Froid", "big", 3),
      row(2, "supplier", "Fournisseur", "big", 5),
    ]);

    expect(boxSummary(holders).big.own).toBe(-2);
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

describe("boxCountsFromInputs", () => {
  test("blank and zero inputs send nothing: an empty form posts no boxes", () => {
    expect(boxCountsFromInputs(NO_BOX_INPUTS)).toEqual({ counts: {}, invalid: [] });
    expect(boxCountsFromInputs({ small: " 0 ", big: "00" })).toEqual({ counts: {}, invalid: [] });
  });

  test("sends the whole counts of the types typed", () => {
    expect(boxCountsFromInputs({ small: "12", big: "" })).toEqual({ counts: { small: 12 }, invalid: [] });
    expect(boxCountsFromInputs({ small: "3", big: " 40 " })).toEqual({ counts: { small: 3, big: 40 }, invalid: [] });
  });

  test("names the types typed as a decimal, a minus sign or a word, and sends none of them", () => {
    expect(boxCountsFromInputs({ small: "1,5", big: "-2" })).toEqual({ counts: {}, invalid: ["small", "big"] });
    expect(boxCountsFromInputs({ small: "dix", big: "4" })).toEqual({ counts: { big: 4 }, invalid: ["small"] });
  });
});

describe("boxInputsFromCounts", () => {
  test("shows the saved counts, and an empty input for a type with none", () => {
    expect(boxInputsFromCounts({ small: 6 })).toEqual({ small: "6", big: "" });
    expect(boxInputsFromCounts({ small: 0, big: 2 })).toEqual({ small: "", big: "2" });
    expect(boxInputsFromCounts(undefined)).toEqual(NO_BOX_INPUTS);
  });
});
