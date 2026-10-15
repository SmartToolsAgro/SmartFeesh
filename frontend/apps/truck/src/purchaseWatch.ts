import type { MyFieldPurchase } from "@frutti/api";
import { useEffect, useState } from "react";

// The office's decisions on the driver's purchases at the port (D-158): each validated or refused purchase is
// announced on every screen until the driver says they read it. What they read is kept on the phone.

const STORAGE_KEY = "frutti-truck-purchases-read";
/** A decision older than this is not announced any more (an old phone, a first login). */
const RECENT_MS = 3 * 24 * 60 * 60 * 1000;

let read: number[] | null = null;
const listeners = new Set<() => void>();

function readIds(): number[] {
  if (read !== null) return read;
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    read = Array.isArray(parsed) ? parsed.filter((id): id is number => typeof id === "number") : [];
  } catch {
    read = [];
  }
  return read;
}

function writeIds(next: number[]): void {
  read = next;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Not kept on the phone: the memory copy holds for this session.
  }
  listeners.forEach((listener) => listener());
}

/** The purchases the office decided lately and the driver has not read yet. */
export function decisionsToRead(purchases: readonly MyFieldPurchase[], seen: readonly number[], now: number) {
  return purchases.filter(
    (purchase) =>
      purchase.status !== "submitted" &&
      purchase.decided_at !== null &&
      now - Date.parse(purchase.decided_at) < RECENT_MS &&
      !seen.includes(purchase.id),
  );
}

/** The decisions on screen, kept up to date. */
export function usePurchaseDecisions(purchases: readonly MyFieldPurchase[] | undefined): MyFieldPurchase[] {
  const [seen, setSeen] = useState<number[]>(readIds);
  // The moment the screen opened: recent enough to tell which decisions are still new.
  const [now] = useState(() => Date.now());
  useEffect(() => {
    const update = () => setSeen(readIds());
    listeners.add(update);
    return () => {
      listeners.delete(update);
    };
  }, []);
  return decisionsToRead(purchases ?? [], seen, now);
}

/** The driver read the office's decision on this purchase. The list keeps the last 100 read. */
export function markDecisionRead(purchaseId: number): void {
  writeIds([...readIds().filter((id) => id !== purchaseId), purchaseId].slice(-100));
}

/** Logout: nothing of the last driver's purchases stays on this phone. */
export function forgetPurchaseWatch(): void {
  read = null;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing was kept.
  }
  listeners.forEach((listener) => listener());
}
