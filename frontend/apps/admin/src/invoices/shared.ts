import type { InvoiceStatusEnum } from "@frutti/api";
import type { Session } from "@frutti/auth";
import type { QueryClient } from "@tanstack/react-query";

/** After an invoice or a credit note changes, refresh invoices, credit notes and sales (their invoice link). */
export function refreshAfterInvoice(queryClient: QueryClient) {
  const prefixes = ["/api/v1/invoices", "/api/v1/credit-notes", "/api/v1/sales"];
  return queryClient.invalidateQueries({
    predicate: (query) =>
      typeof query.queryKey[0] === "string" && prefixes.some((prefix) => String(query.queryKey[0]).startsWith(prefix)),
  });
}

/** The server refuses invoices from the accountant; this only avoids showing buttons that would fail. */
export function canInvoice(session: Session): boolean {
  return session.role === "owner" || session.role === "manager";
}

export const INVOICE_STATUSES: InvoiceStatusEnum[] = ["draft", "issued", "cancelled"];

export const STATUS_TONES = {
  draft: "neutral",
  issued: "good",
  cancelled: "bad",
} as const satisfies Record<InvoiceStatusEnum, string>;

export const isZero = (value: string | null | undefined) => !value || /^0+(\.0+)?$/.test(value);
