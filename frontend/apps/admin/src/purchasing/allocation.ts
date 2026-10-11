// How much of a payment goes on each invoice, previewed in the browser with exact thousandths
// (see lib/decimal.ts). The server checks the same rules again.
import type { SupplierInvoice } from "@frutti/api";
import { parseDecimalInput } from "@frutti/i18n";

import { fromThousandths, toThousandths } from "../lib/decimal";

/** The amounts typed per invoice id ("500,5"), as the person typed them. */
export type Allocations = Record<number, string>;

/** Spread `amount` over invoices in the given order (oldest due date first): each gets what it still owes,
 * until the amount runs out. Returns one decimal string per invoice, "" where nothing goes. */
export function spread(amount: string, outstanding: readonly string[]): string[] {
  let left = toThousandths(amount);
  return outstanding.map((owed) => {
    const share = left < toThousandths(owed) ? left : toThousandths(owed);
    if (share <= 0n) return "";
    left -= share;
    return fromThousandths(share);
  });
}

/** -1, 0 or 1 as `a` is smaller than, equal to or larger than `b`. */
export function compare(a: string, b: string): -1 | 0 | 1 {
  const difference = toThousandths(a) - toThousandths(b);
  return difference < 0n ? -1 : difference > 0n ? 1 : 0;
}

/** Open invoices sorted the way a payment settles them: oldest due date first. */
export function byDueDate(invoices: readonly SupplierInvoice[]): SupplierInvoice[] {
  return [...invoices].sort(
    (a, b) => a.due_date.localeCompare(b.due_date) || a.invoice_date.localeCompare(b.invoice_date) || a.id - b.id,
  );
}

export type AllocationProblem = "money" | "positive" | "tooMuch";

/** What the browser can already say about one typed allocation; the server checks again. */
export function allocationProblem(typed: string, invoice: SupplierInvoice): AllocationProblem | null {
  if (typed.trim() === "") return null;
  const value = parseDecimalInput(typed.trim(), 3);
  if (value === null || value.startsWith("-")) return "money";
  if (compare(value, "0") === 0) return "positive";
  if (compare(value, invoice.outstanding) > 0) return "tooMuch";
  return null;
}

/** True when one of the typed allocations is already known to be refused. */
export function hasAllocationProblem(invoices: readonly SupplierInvoice[], values: Allocations): boolean {
  return invoices.some((invoice) => allocationProblem(values[invoice.id] ?? "", invoice) !== null);
}

/** The allocations to send: the invoices with an amount, in table order, as API decimals. Null when one is
 * not a readable amount (its error is shown on its row). */
export function allocationPayload(
  invoices: readonly SupplierInvoice[],
  values: Allocations,
): { invoice: number; amount: string }[] | null {
  const payload: { invoice: number; amount: string }[] = [];
  for (const invoice of invoices) {
    const typed = (values[invoice.id] ?? "").trim();
    if (typed === "") continue;
    const amount = parseDecimalInput(typed, 3);
    if (amount === null) return null;
    payload.push({ invoice: invoice.id, amount });
  }
  return payload;
}

/** Server errors on `allocations.<index>.<field>` moved onto the invoice of that line. */
export function errorsByInvoice(
  serverErrors: Record<string, string>,
  sent: readonly { invoice: number }[],
): Record<number, string> {
  const result: Record<number, string> = {};
  for (const [key, message] of Object.entries(serverErrors)) {
    const match = /^allocations\.(\d+)\.\w+$/.exec(key);
    const line = match ? sent[Number(match[1])] : undefined;
    if (line) result[line.invoice] = message;
  }
  return result;
}

/** API decimals for display in an input, the way people type them here: "500.000" → "500,000". */
export const asTyped = (value: string) => value.replace(".", ",");
