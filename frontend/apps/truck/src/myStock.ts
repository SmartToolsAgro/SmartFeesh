import { useListMyStock } from "@frutti/api";
import { keepPreviousData } from "@tanstack/react-query";

/** The truck's stock and today's prices are asked again every minute while the phone is online (P3-T02). */
export const STOCK_REFRESH_MS = 60_000;

/**
 * The truck's stock and the price per product: one query, shared by every screen that shows prices. With a `customer`,
 * the price that customer pays (their own price list first, D-049); the daily prices stay on screen while it loads.
 */
export function useTruckStock(enabled: boolean, customer?: number) {
  return useListMyStock(customer === undefined ? undefined : { customer }, {
    query: {
      enabled,
      retry: false,
      refetchInterval: () => (navigator.onLine ? STOCK_REFRESH_MS : false),
      refetchOnWindowFocus: true,
      placeholderData: keepPreviousData,
    },
  });
}
