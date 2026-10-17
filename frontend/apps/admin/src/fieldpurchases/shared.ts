import type { FieldPurchaseStatusEnum, PaymentTermsEnum, RevisionChange } from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";

/** After a purchase at the port is saved, validated or refused: its lists, and everything a validation records
 * (receipt, stock, invoice, payments, balances, the dashboard alert). */
export function refreshAfterFieldPurchase(queryClient: QueryClient) {
  const prefixes = [
    "/api/v1/field-purchases",
    "/api/v1/receipts",
    "/api/v1/supplier-invoices",
    "/api/v1/supplier-payments",
    "/api/v1/supplier-balances",
    "/api/v1/batches",
    "/api/v1/locations",
    "/api/v1/dashboard",
  ];
  return queryClient.invalidateQueries({
    predicate: (query) =>
      typeof query.queryKey[0] === "string" && prefixes.some((prefix) => String(query.queryKey[0]).startsWith(prefix)),
  });
}

/** Amber to check, green validated, grey refused. */
export const STATUS_TONE: Record<FieldPurchaseStatusEnum, "warn" | "good" | "neutral"> = {
  submitted: "warn",
  validated: "good",
  refused: "neutral",
};

/** The due date of a deal, as the server computes it (D-175): the day itself, N days later, or the end of the
 * month + N days. Calendar dates only, no time zone. */
export function dueDateOf(boughtOn: string, terms: PaymentTermsEnum, days: number): string {
  const [year, month, day] = boughtOn.split("-").map(Number);
  if (!year || !month || !day) return boughtOn;
  const at = (y: number, m: number, d: number) => new Date(Date.UTC(y, m, d)).toISOString().slice(0, 10);
  if (terms === "days") return at(year, month - 1, day + days);
  // Day 0 of the next month is the last day of this one.
  if (terms === "month_end") return at(year, month, days);
  return boughtOn;
}

/** The fields a revision's changes name, each with its label under `admin.fieldPurchases.history.fields`. */
export const HISTORY_FIELDS = [
  "supplier",
  "proposed_supplier",
  "proposed_supplier_phone",
  "bought_on",
  "terms",
  "due_days",
  "supplier_reference",
  "notes",
  "location",
  "boxes.small",
  "boxes.big",
  "product",
  "proposed_product",
  "declared_quantity",
  "received_quantity",
  "unit_cost",
  "partner",
  "method",
  "amount",
  "reference",
  "cash_on",
] as const;
export type HistoryField = (typeof HISTORY_FIELDS)[number];

export function isHistoryField(value: string): value is HistoryField {
  return (HISTORY_FIELDS as readonly string[]).includes(value);
}

/** How a change reads: on the purchase ("bought_on"), on a line ("lines.unit_cost", position 0) or on a payment,
 * or a line or payment added or removed. */
export type ChangeShape =
  | { kind: "header"; field: string }
  | { kind: "row"; row: "line" | "payment"; number: number; field: string }
  | { kind: "added"; row: "line" | "payment"; number: number }
  | { kind: "removed"; row: "line" | "payment"; number: number };

export function shapeOf(change: RevisionChange): ChangeShape {
  const [prefix, rest] = change.field.split(/\.(.*)/s, 2) as [string, string | undefined];
  if ((prefix === "lines" || prefix === "payments") && rest !== undefined) {
    const row = prefix === "lines" ? "line" : "payment";
    const number = (change.line ?? 0) + 1;
    if (rest === "added") return { kind: "added", row, number };
    if (rest === "removed") return { kind: "removed", row, number };
    return { kind: "row", row, number, field: rest };
  }
  return { kind: "header", field: change.field };
}
