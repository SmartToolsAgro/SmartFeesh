import { currentLanguage, i18n, type Language } from "./i18n";

// Tunisian conventions: 1 250,000 in French, 1.250,000 in Arabic, always with Western digits.
const LOCALES: Record<Language, string> = { fr: "fr-TN", ar: "ar-TN" };
const NO_BREAK_SPACE = " ";

/** A decimal as the API sends it, e.g. "1250.000". Never a JavaScript number (ARCHITECTURE §4.1). */
type DecimalString = string;

function threeDecimals(value: DecimalString, language: Language): string {
  if (!/^-?\d+(\.\d+)?$/.test(value)) throw new TypeError(`Not a decimal string: ${JSON.stringify(value)}`);
  const formatter = new Intl.NumberFormat(LOCALES[language], { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  // Given a string, Intl formats the exact decimal: no float is ever created.
  return formatter.format(value as Intl.StringNumericLiteral);
}

/** "1250" → "1 250,000 DT" */
export function formatMoney(amount: DecimalString, language: Language = currentLanguage()): string {
  return `${threeDecimals(amount, language)}${NO_BREAK_SPACE}${i18n.t("common.currency", { lng: language })}`;
}

/** "12.5" → "12,500 kg" */
export function formatQuantity(kilograms: DecimalString, language: Language = currentLanguage()): string {
  return `${threeDecimals(kilograms, language)}${NO_BREAK_SPACE}kg`;
}

/** "2026-10-09" or a full ISO timestamp → "09/10/2026", read in Tunisian time. */
export function formatDate(iso: string, language: Language = currentLanguage()): string {
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(iso);
  const date = new Date(dateOnly ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(date.getTime())) throw new TypeError(`Not an ISO date: ${JSON.stringify(iso)}`);
  return new Intl.DateTimeFormat(LOCALES[language], {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    // A plain date has no time zone; a timestamp is shown in the company's time.
    timeZone: dateOnly ? "UTC" : "Africa/Tunis",
  }).format(date);
}
