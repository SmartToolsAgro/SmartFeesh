import type { Session } from "@frutti/auth";
import type { QueryClient } from "@tanstack/react-query";

/** Every cached answer about customers (list and detail) is refreshed after a change. */
export function refreshCustomers(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (query) => typeof query.queryKey[0] === "string" && query.queryKey[0].startsWith("/api/v1/customers"),
  });
}

/** The server refuses changes from other roles; this only avoids showing buttons that would fail. */
export function canEditCustomers(session: Session): boolean {
  return session.role === "owner" || session.role === "manager";
}
