import type { Product } from "@frutti/api";
import { formatTemperature, i18n } from "@frutti/i18n";
import type { QueryClient } from "@tanstack/react-query";

/** Every cached answer about products (list, detail, prices) is refreshed after a change. */
export function refreshProducts(queryClient: QueryClient) {
  return queryClient.invalidateQueries({
    predicate: (query) => typeof query.queryKey[0] === "string" && query.queryKey[0].startsWith("/api/v1/products"),
  });
}

/** "0 à 4 °C", "≤ -18 °C", or null when the product has no storage temperature. */
export function storageRange(product: Pick<Product, "storage_temp_min" | "storage_temp_max">): string | null {
  const { storage_temp_min: low, storage_temp_max: high } = product;
  if (low !== null && high !== null) {
    return i18n.t("admin.products.temperature.range", {
      min: formatTemperature(low).replace(/\s°C$/, ""),
      max: formatTemperature(high),
    });
  }
  if (high !== null) return i18n.t("admin.products.temperature.atMost", { max: formatTemperature(high) });
  if (low !== null) return i18n.t("admin.products.temperature.atLeast", { min: formatTemperature(low) });
  return null;
}
