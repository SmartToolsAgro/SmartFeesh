import type { ExpenseStatusEnum, PaymentMethodEnum, WorkTypeEnum } from "@frutti/api";
import type { Session } from "@frutti/auth";
import type { QueryClient } from "@tanstack/react-query";

/** After an expense or a day worked changes, refresh every list that shows them (and lot costs). */
export function refreshExpenses(queryClient: QueryClient) {
  const prefixes = [
    "/api/v1/expenses",
    "/api/v1/expense-categories",
    "/api/v1/day-labour",
    "/api/v1/day-labourers",
    "/api/v1/lot-costs",
  ];
  return queryClient.invalidateQueries({
    predicate: (query) =>
      typeof query.queryKey[0] === "string" && prefixes.some((prefix) => String(query.queryKey[0]).startsWith(prefix)),
  });
}

/** Owner and manager record and approve; the accountant reads. The server checks it too. */
export function canWriteExpenses(session: Session): boolean {
  return session.role === "owner" || session.role === "manager";
}

/** Only the owner manages the categories (checked by the server too). */
export function canManageCategories(session: Session): boolean {
  return session.role === "owner";
}

export const EXPENSE_STATUSES: ExpenseStatusEnum[] = ["draft", "pending", "approved", "rejected"];

export const EXPENSE_TONES = {
  draft: "neutral",
  pending: "warn",
  approved: "good",
  rejected: "bad",
} as const satisfies Record<ExpenseStatusEnum, string>;

export const PAYMENT_METHODS: PaymentMethodEnum[] = ["cash", "cheque", "transfer", "bill", "other"];

export const WORK_TYPES: WorkTypeEnum[] = ["loading", "stock", "store", "cleaning", "other"];

/** A draft or an expense sent for approval: it can still change, be approved or refused. */
export function isOpen(status: ExpenseStatusEnum): boolean {
  return status === "draft" || status === "pending";
}
