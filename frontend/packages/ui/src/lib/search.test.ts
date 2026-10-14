import { expect, test } from "vitest";

import { searchOptions } from "./search";

const products = [
  { label: "Crevette royale · ART0002", keywords: ["روبيان", "Crustacés"] },
  { label: "Sardine · SA-010", keywords: ["سردين", "Poissons bleus"] },
  { label: "Dorade royale · DO-003", keywords: ["Poissons blancs"] },
  { label: "Calamar · CA-005", keywords: ["Céphalopodes"] },
];
const found = (query: string) => searchOptions(products, query).map((option) => option.label);

test("nothing typed keeps every option, in its order", () => {
  expect(found("  ")).toEqual(products.map((option) => option.label));
});

test("an option is found by its name, whatever the case and the accents", () => {
  expect(found("CREV")).toEqual(["Crevette royale · ART0002"]);
  expect(found("cephalo")).toEqual(["Calamar · CA-005"]);
});

test("an option is found by its code, typed with or without its dash", () => {
  expect(found("sa-010")).toEqual(["Sardine · SA-010"]);
  expect(found("sa010")).toEqual(["Sardine · SA-010"]);
  expect(found("art0002")).toEqual(["Crevette royale · ART0002"]);
});

test("an option is found by a keyword: its category or its Arabic name", () => {
  expect(found("poissons")).toEqual(["Sardine · SA-010", "Dorade royale · DO-003"]);
  expect(found("سردين")).toEqual(["Sardine · SA-010"]);
});

test("every word typed must be found, in any order", () => {
  expect(found("royale do")).toEqual(["Dorade royale · DO-003"]);
  expect(found("royale sardine")).toEqual([]);
});

test("a name that starts with what is typed comes first, then a word that does, then the rest", () => {
  // "ca" starts "Carpe", starts the code "CA-9" of the bar, and is only inside "esCArgot".
  const fish = [{ label: "Escargot" }, { label: "Bar · CA-9" }, { label: "Carpe" }];
  expect(searchOptions(fish, "ca").map((option) => option.label)).toEqual(["Carpe", "Bar · CA-9", "Escargot"]);
  // Enter takes the first one: "ro" is the rouget before the crevette royale.
  const royals = [{ label: "Crevette Royale · CR-001" }, { label: "Rouget · RO-009" }];
  expect(searchOptions(royals, "ro").map((option) => option.label)).toEqual([
    "Rouget · RO-009",
    "Crevette Royale · CR-001",
  ]);
});
