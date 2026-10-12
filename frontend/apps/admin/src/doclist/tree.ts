import type { DocumentRow, DocumentTypeEnum } from "@frutti/api";

/** One line of the "Documents" table: the document, how deep it sits in its chain, and whether it has children. */
export interface TreeLine {
  row: DocumentRow;
  depth: number;
  childCount: number;
}

export const SALES_TYPES: DocumentTypeEnum[] = ["DV", "BL", "FA", "AV"];
export const PURCHASE_TYPES: DocumentTypeEnum[] = ["BA", "BR", "FF"];

/**
 * The rows as chains: each document under the first of its parents that is in the list (DV → BL → FA → AV,
 * BA → BR → FF). A document whose parents are all outside the list (another period) starts a chain of its own.
 * Chains keep the server's order (newest first); children read in the order they happened (oldest first).
 * The descendants of a key in `collapsed` are left out.
 */
export function buildTree(rows: DocumentRow[], collapsed: ReadonlySet<string> = new Set()): TreeLine[] {
  const present = new Set(rows.map((row) => row.key));
  const children = new Map<string, DocumentRow[]>();
  const roots: DocumentRow[] = [];
  for (const row of rows) {
    const parent = row.parents.find((key) => present.has(key));
    if (parent === undefined) roots.push(row);
    else children.set(parent, [...(children.get(parent) ?? []), row]);
  }
  const lines: TreeLine[] = [];
  const seen = new Set<string>();
  const walk = (row: DocumentRow, depth: number) => {
    // A broken chain (a document listed as its own ancestor) must not loop forever.
    if (seen.has(row.key)) return;
    seen.add(row.key);
    const kids = [...(children.get(row.key) ?? [])].reverse();
    lines.push({ row, depth, childCount: kids.length });
    if (!collapsed.has(row.key)) for (const kid of kids) walk(kid, depth + 1);
  };
  for (const root of roots) walk(root, 0);
  return lines;
}

/** The rows of the list view: no nesting. */
export function flatLines(rows: DocumentRow[]): TreeLine[] {
  return rows.map((row) => ({ row, depth: 0, childCount: 0 }));
}

/** "BL:12" → ["BL", 12]. */
export function parseKey(key: string): [DocumentTypeEnum, number] {
  const [type, id] = key.split(":");
  return [type as DocumentTypeEnum, Number(id)];
}

/** Where a document's own page is. A credit note has none: it shows on its invoice's page. */
export function detailPath(row: DocumentRow): string {
  switch (row.type) {
    case "DV":
      return `/devis/${row.id}`;
    case "BL":
      return `/ventes/${row.id}`;
    case "FA":
      return `/factures/${row.id}`;
    case "AV": {
      const invoice = row.parents[0];
      return invoice ? `/factures/${parseKey(invoice)[1]}` : "/factures";
    }
    case "BA":
      return `/achats/bons/${row.id}`;
    case "BR":
      return `/achats/${row.id}`;
    case "FF":
      return `/achats/factures/${row.id}`;
  }
}
