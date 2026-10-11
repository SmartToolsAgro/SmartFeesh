// Month grids for the day-labour calendar, on plain "YYYY-MM-DD" strings (UTC dates, so no time zone or
// summer-time shift can move a day).

export interface Month {
  year: number;
  /** 1 to 12. */
  month: number;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function isoDay(year: number, month: number, day: number): string {
  return `${year}-${pad(month)}-${pad(day)}`;
}

/** The month a "YYYY-MM-DD" day belongs to. */
export function monthOf(day: string): Month {
  const [year = "1970", month = "1"] = day.split("-");
  return { year: Number(year), month: Number(month) };
}

/** The month `offset` months after (or before, when negative) `month`. */
export function addMonths({ year, month }: Month, offset: number): Month {
  const index = year * 12 + (month - 1) + offset;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

export function daysIn({ year, month }: Month): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** First and last day of the month, both included. */
export function monthBounds(month: Month): { first: string; last: string } {
  return { first: isoDay(month.year, month.month, 1), last: isoDay(month.year, month.month, daysIn(month)) };
}

/** The weeks of a month, Monday first: each week has 7 cells, a day ("YYYY-MM-DD") or null outside the month. */
export function weeksOf(month: Month): (string | null)[][] {
  // getUTCDay: 0 = Sunday … 6 = Saturday; turned into 0 = Monday … 6 = Sunday.
  const lead = (new Date(Date.UTC(month.year, month.month - 1, 1)).getUTCDay() + 6) % 7;
  const cells: (string | null)[] = Array.from({ length: lead }, () => null);
  for (let day = 1; day <= daysIn(month); day += 1) cells.push(isoDay(month.year, month.month, day));
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (string | null)[][] = [];
  for (let start = 0; start < cells.length; start += 7) weeks.push(cells.slice(start, start + 7));
  return weeks;
}

/** "octobre 2026" in the given language. */
export function monthLabel(month: Month, language: string): string {
  return new Intl.DateTimeFormat(language, { month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(month.year, month.month - 1, 1)),
  );
}

/** Short names of the weekdays, Monday first ("lun.", "mar."...), in the given language. */
export function weekdayLabels(language: string): string[] {
  const format = new Intl.DateTimeFormat(language, { weekday: "short", timeZone: "UTC" });
  // 2024-01-01 was a Monday.
  return Array.from({ length: 7 }, (_, index) => format.format(new Date(Date.UTC(2024, 0, 1 + index))));
}
