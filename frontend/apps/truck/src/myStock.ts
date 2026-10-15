import { useListMyStock } from "@frutti/api";

/** The truck's stock and today's prices are asked again every minute while the phone is online (P3-T02). */
export const STOCK_REFRESH_MS = 60_000;

/** The truck's stock and today's price per product: one query, shared by every screen that shows prices. */
export function useTruckStock(enabled: boolean) {
  return useListMyStock({
    query: {
      enabled,
      retry: false,
      refetchInterval: () => (navigator.onLine ? STOCK_REFRESH_MS : false),
      refetchOnWindowFocus: true,
    },
  });
}
