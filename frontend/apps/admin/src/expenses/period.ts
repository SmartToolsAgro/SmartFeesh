// The dates the expenses list shows, on plain "YYYY-MM-DD" strings.

import { monthRange } from "../closing/month";

/** One calendar month (its first day, "2026-10-01"), or a free period whose empty bound is open. */
export type Period = { mode: "month"; month: string } | { mode: "period"; from: string; to: string };

/** A day as the API writes it, or "" for anything else (an address typed by hand). */
function isoDay(value: string | null): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) ? value : "";
}

const monthOf = (day: string) => `${day.slice(0, 7)}-01`;

/** What the list opens on: the dates of the link that led here (the month closing's cost lines, D-122), as a
 * month when they cover exactly one; this month without a link. */
export function openingPeriod(dateFrom: string | null, dateTo: string | null, thisMonth: string): Period {
  const from = isoDay(dateFrom);
  const to = isoDay(dateTo);
  if (!from && !to) return { mode: "month", month: thisMonth };
  if (from === monthOf(from) && monthRange(from).to === to) return { mode: "month", month: from };
  return { mode: "period", from, to };
}

/** The `date_from` and `date_to` to ask the server for: both included, absent when open. */
export function periodDates(period: Period): { date_from?: string; date_to?: string } {
  const { from, to } = period.mode === "month" ? monthRange(period.month) : period;
  return { ...(from ? { date_from: from } : {}), ...(to ? { date_to: to } : {}) };
}

/** From the month to a period: the same dates, ready to be changed. */
export function asPeriod(period: Period): Period {
  return period.mode === "period" ? period : { mode: "period", ...monthRange(period.month) };
}

/** Back to the month: the one the period starts in, else ends in, else this month. Never after this month,
 * since no expense is dated in the future. */
export function asMonth(period: Period, thisMonth: string): Period {
  if (period.mode === "month") return period;
  const day = isoDay(period.from) || isoDay(period.to);
  const month = day ? monthOf(day) : thisMonth;
  return { mode: "month", month: month < thisMonth ? month : thisMonth };
}
