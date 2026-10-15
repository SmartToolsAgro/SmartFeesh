/**
 * The entries a dropdown offers: the active ones, plus an archived one that a saved record already points at,
 * so the field never shows blank (D-137). `current` holds the ids the form has chosen, `undefined` or "" when none.
 */
export function pickable<T extends { id: number; is_active: boolean }>(
  items: readonly T[],
  current: readonly (string | number | null | undefined)[],
): T[] {
  const kept = new Set(current.filter((value) => value !== undefined && value !== null && value !== "").map(String));
  return items.filter((item) => item.is_active || kept.has(String(item.id)));
}
