const KEY = "frutti-truck-recent-customers";
const KEPT = 5;

/** The customers this phone sold to most recently, newest first. Kept on this phone only (D-168). */
export function recentCustomerIds(): number[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter((id): id is number => typeof id === "number").slice(0, KEPT) : [];
  } catch {
    // Storage blocked or damaged: no recent customers, the full list still works.
    return [];
  }
}

/** Puts a customer first in the recent list. Storage refused: the list just does not grow. */
export function rememberCustomer(id: number): void {
  try {
    const next = [id, ...recentCustomerIds().filter((one) => one !== id)].slice(0, KEPT);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Not saved.
  }
}

/** Forget the list, so the next person on this phone does not see the last one's customers. */
export function forgetRecentCustomers(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing saved to forget.
  }
}
