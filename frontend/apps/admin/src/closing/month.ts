/** "2026-10-01" → "2026-10", the address of a month in the API. */
export const monthKey = (day: string) => day.slice(0, 7);

/** The month as people say it: "octobre 2026". */
export function monthLabel(day: string): string {
  const [year, month] = day.split("-");
  return new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
}
