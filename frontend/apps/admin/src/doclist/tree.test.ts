import type { DocumentRow } from "@frutti/api";
import { describe, expect, it } from "vitest";

import { buildTree, detailPath } from "./tree";

function row(key: string, parents: string[] = [], date = "2026-10-04"): DocumentRow {
  const [type, id] = key.split(":");
  return {
    key,
    type: type as DocumentRow["type"],
    id: Number(id),
    number: key,
    partner_side: "customer",
    partner_id: 1,
    partner_name: "Restaurant Le Corail",
    date,
    amount: "10.000",
    status: "confirmed",
    status_label: "Confirmée",
    tone: "done",
    parents,
    actions: [],
    pdf: "",
  };
}

const keys = (rows: DocumentRow[], collapsed?: Set<string>) =>
  buildTree(rows, collapsed).map(({ row: { key }, depth }) => `${"  ".repeat(depth)}${key}`);

describe("buildTree", () => {
  // Newest first, as the server sends them.
  const rows = [
    row("FA:1", ["BL:2"]),
    row("BL:2", ["DV:1"]),
    row("BL:1", ["DV:1"]),
    row("DV:1"),
    row("FF:1", ["BR:1", "BR:2"]),
    row("BR:2"),
    row("BR:1", ["BA:9"]),
  ];

  it("puts each document under its parent, children oldest first", () => {
    expect(keys(rows)).toEqual(["DV:1", "  BL:1", "  BL:2", "    FA:1", "BR:2", "BR:1", "  FF:1"]);
  });

  it("files a document with several parents under the first one in the list", () => {
    // BR:1 (its order BA:9 is outside the list) is a root and holds FF:1; without it, FF:1 goes under BR:2.
    expect(keys(rows.filter((item) => item.key !== "BR:1")).slice(-2)).toEqual(["BR:2", "  FF:1"]);
  });

  it("hides the descendants of a collapsed document", () => {
    expect(keys(rows, new Set(["DV:1"]))).toEqual(["DV:1", "BR:2", "BR:1", "  FF:1"]);
  });

  it("counts children", () => {
    expect(buildTree(rows).find((line) => line.row.key === "DV:1")?.childCount).toBe(2);
  });
});

describe("detailPath", () => {
  it("sends a credit note to its invoice's page", () => {
    expect(detailPath(row("AV:3", ["FA:7"]))).toBe("/factures/7");
    expect(detailPath(row("BA:4"))).toBe("/achats/bons/4");
  });
});
