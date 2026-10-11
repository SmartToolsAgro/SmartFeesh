import type { Session } from "@frutti/auth";
import type { QueryClient } from "@tanstack/react-query";

/** After a payment or a certificate changes: payments, balances, ageing, sales and invoices all move. */
export function refreshAfterPayment(queryClient: QueryClient) {
  const prefixes = [
    "/api/v1/customer-payments",
    "/api/v1/customers",
    "/api/v1/receivables",
    "/api/v1/sales",
    "/api/v1/invoices",
    "/api/v1/withholding",
  ];
  return queryClient.invalidateQueries({
    predicate: (query) =>
      typeof query.queryKey[0] === "string" && prefixes.some((prefix) => String(query.queryKey[0]).startsWith(prefix)),
  });
}

/** The server refuses payments from the accountant; this only avoids showing buttons that would fail. */
export function canCollect(session: Session): boolean {
  return session.role === "owner" || session.role === "manager";
}

/** A moment of today as the API expects ("2026-10-11"), from the browser's local day. */
export function todayInput(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
