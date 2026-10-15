// The stock of each place, read together, so a seller picks the product first and the place comes after (D-144).

import { getListLocationStockQueryKey, listLocationStock } from "@frutti/api";
import { parseDecimalInput } from "@frutti/i18n";
import { useQueries } from "@tanstack/react-query";

import { sum, toThousandths } from "./decimal";
import { isShort, isZero, type Line } from "./lines";

/** Kilos per place: place id → product id → kg, as the server counts them. */
export type StockByPlace = Map<number, Map<string, string>>;

/** The rows of a sale that name a product and a weight: what the sale has to take out of one place. */
export type Need = { product: string; kg: string };

/** The needs of the rows typed in: a row without a product or a positive weight takes nothing yet. */
export function needsOf(rows: readonly Line[]): Need[] {
  return rows.flatMap((line) => {
    const kg = parseDecimalInput(line.quantity.trim(), 3);
    return line.product && kg !== null && !kg.startsWith("-") && !isZero(kg) ? [{ product: line.product, kg }] : [];
  });
}

/** The kilos one product holds in one place, by the place's name. */
export type PlaceKilos = { place: string; kg: string };

const stockQueries = (placeIds: number[]) =>
  placeIds.map((id) => ({
    queryKey: getListLocationStockQueryKey(id),
    queryFn: () => listLocationStock(id),
  }));

/** The stock of every place given, loaded together. */
export function usePlacesStock(placeIds: number[]): StockByPlace {
  const results = useQueries({ queries: stockQueries(placeIds) });
  const byPlace: StockByPlace = new Map();
  placeIds.forEach((id, index) => {
    const byProduct = new Map<string, string>();
    for (const row of results[index]?.data ?? []) byProduct.set(String(row.product_id), row.quantity);
    byPlace.set(id, byProduct);
  });
  return byPlace;
}

/** True once the stock of every place given has loaded; until then no product shows where it is kept. */
export function usePlacesStockLoaded(placeIds: number[]): boolean {
  const results = useQueries({ queries: stockQueries(placeIds) });
  return results.every((result) => result.isSuccess);
}

/** Where each product is kept: the places holding it, fullest first, each named as the office names it. */
export function placesOf(byPlace: StockByPlace, names: Map<number, string>): Map<string, PlaceKilos[]> {
  const byProduct = new Map<string, PlaceKilos[]>();
  for (const [id, places] of byPlace) {
    for (const [product, kg] of places) {
      if (toThousandths(kg) <= 0n) continue;
      byProduct.set(product, [...(byProduct.get(product) ?? []), { place: names.get(id) ?? "", kg }]);
    }
  }
  for (const list of byProduct.values()) list.sort((a, b) => Number(toThousandths(b.kg) - toThousandths(a.kg)));
  return byProduct;
}

/** Kilos per product over all the places: what the seller sees next to the product. */
export function totalsOf(byPlace: StockByPlace): Map<string, string> {
  const products = new Set([...byPlace.values()].flatMap((byProduct) => [...byProduct.keys()]));
  return new Map(
    [...products].map((product) => [product, sum([...byPlace.values()].map((places) => places.get(product) ?? "0"))]),
  );
}

/**
 * The one place a sale leaves from: the place that holds every row's kilos, the fullest one first. `null` when no
 * single place holds all of them: a sale takes its kilos from one place only, so the seller splits it.
 */
export function choosePlace(needs: Need[], byPlace: StockByPlace): number | null {
  if (needs.length === 0) return null;
  const fits = (id: number) => needs.every((need) => !isShort(need.kg, byPlace.get(id)?.get(need.product) ?? "0"));
  const fullest = (id: number) => sum([...(byPlace.get(id)?.values() ?? [])]);
  const candidates = [...byPlace.keys()].filter(fits);
  candidates.sort((a, b) => (toThousandths(fullest(b)) > toThousandths(fullest(a)) ? 1 : -1));
  return candidates[0] ?? null;
}
