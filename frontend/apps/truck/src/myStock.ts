import { type MyStockLine, useListMyStock } from "@frutti/api";
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

/**
 * Nothing left to sell: every product on the truck is gone or already promised to a sale, delivery or loss still
 * waiting to be sent. The office names the clients when it loads the truck, so an empty truck has no client (D-184).
 */
export function truckIsEmpty(lines: readonly MyStockLine[], promised: Record<number, number>) {
  return lines.every((line) => Number(line.quantity) - (promised[line.product_id] ?? 0) <= 0.0005);
}
