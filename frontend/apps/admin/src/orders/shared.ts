import type { PurchaseOrderStatusEnum } from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";

/** The pill colour of each order status: grey waiting or finished by hand, amber partly, green received. */
export const ORDER_TONE: Record<PurchaseOrderStatusEnum, "neutral" | "sea" | "warn" | "good"> = {
  open: "sea",
  partly_received: "warn",
  received: "good",
  closed: "neutral",
  cancelled: "neutral",
};

/** After an order is closed or cancelled, refresh orders and receipts (a receipt shows its order's status). */
export function refreshOrders(queryClient: QueryClient) {
  const prefixes = ["/api/v1/purchase-orders", "/api/v1/receipts"];
  return queryClient.invalidateQueries({
    predicate: (query) =>
      typeof query.queryKey[0] === "string" && prefixes.some((prefix) => String(query.queryKey[0]).startsWith(prefix)),
  });
}
