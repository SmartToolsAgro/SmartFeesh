import type { MyStockLine } from "@frutti/api";
import { useEffect, useState } from "react";

/** The price per kg the phone last saw of each product, by product id; null when the product had no price. */
type Known = Record<string, string | null>;

const STORAGE_KEY = "frutti-truck-prices";

export interface PriceChange {
  productId: number;
  productName: string;
  from: string | null;
  to: string | null;
}

// What the phone saw before, kept on the phone so a change made while the app was closed is still announced.
// Blocked storage: the memory copy is used for this session only.
let known: Known | null = null;
let notices: PriceChange[] = [];
const listeners = new Set<() => void>();

function publish(next: PriceChange[]): void {
  notices = next;
  listeners.forEach((listener) => listener());
}

/** Prices come back with three decimals, so "45" and "45.000" are the same price. */
function normalize(price: string | null): string | null {
  return price === null ? null : Number(price).toFixed(3);
}

function readKnown(): Known {
  if (known !== null) return known;
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    known = typeof parsed === "object" && parsed !== null ? (parsed as Known) : {};
  } catch {
    known = {};
  }
  return known;
}

function writeKnown(next: Known): void {
  known = next;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Not kept on the phone: the memory copy still holds for this session.
  }
}

/**
 * The products whose price is not the one the phone last saw. A product the phone never saw is not a change: its
 * first price is only remembered.
 */
export function priceChanges(seen: Known, lines: MyStockLine[]): PriceChange[] {
  return lines.flatMap((line) => {
    const key = String(line.product_id);
    if (!(key in seen)) return [];
    const from = seen[key] ?? null;
    const to = normalize(line.unit_price);
    if (from === to) return [];
    return [{ productId: line.product_id, productName: line.product_name, from, to }];
  });
}

/** Adds the changes to the notices on screen; a newer change for a product replaces the older one. */
function addNotices(changes: PriceChange[]): void {
  const kept = notices.filter((notice) => !changes.some((change) => change.productId === notice.productId));
  publish([...kept, ...changes]);
}

/** The price notices on screen, newest last. */
export function usePriceNotices(): PriceChange[] {
  const [current, setCurrent] = useState(notices);
  useEffect(() => {
    const update = () => setCurrent(notices);
    listeners.add(update);
    update();
    return () => {
      listeners.delete(update);
    };
  }, []);
  return current;
}

/** The driver has read the notice about this product's price. */
export function dismissPriceNotice(productId: number): void {
  publish(notices.filter((notice) => notice.productId !== productId));
}

/**
 * Compares each stock answer with the prices seen before and raises a notice for every product whose price moved.
 * The first answer on a phone only remembers the prices.
 */
export function usePriceWatch(lines: MyStockLine[] | undefined): void {
  useEffect(() => {
    if (lines === undefined) return;
    const seen = readKnown();
    const changes = priceChanges(seen, lines);
    if (changes.length > 0) addNotices(changes);
    const latest = Object.fromEntries(lines.map((line) => [String(line.product_id), normalize(line.unit_price)]));
    writeKnown({ ...seen, ...latest });
  }, [lines]);
}

/** Logout: nothing of the last driver's prices or notices stays on this phone. */
export function forgetPriceWatch(): void {
  known = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing was kept.
  }
  publish([]);
}
