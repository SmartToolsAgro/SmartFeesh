import type { BoxTypeEnum } from "@frutti/api";
import { type Language, currentLanguage } from "@frutti/i18n";

// Returnable boxes on the phone (P1-T14d, D-122): whole counts only, never kilos.

export const BOX_TYPES: BoxTypeEnum[] = ["small", "big"];

/** What the driver typed for each box type: the raw text of an input. Empty means none. */
export type BoxInputs = Record<BoxTypeEnum, string>;

export const NO_BOXES: BoxInputs = { small: "", big: "" };

export type BoxCounts = Record<BoxTypeEnum, number>;

/** One count typed by the driver: "" is 0, "3" is 3. A decimal, a sign, letters or a too big number is null. */
export function wholeCount(text: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return 0;
  if (!/^\d+$/.test(trimmed)) return null;
  const value = Number(trimmed);
  return Number.isSafeInteger(value) ? value : null;
}

/** The counts to send, or null when one of them is not a whole number. Zero counts are kept. */
export function boxCountsOf(inputs: BoxInputs): BoxCounts | null {
  const small = wholeCount(inputs.small);
  const big = wholeCount(inputs.big);
  if (small === null || big === null) return null;
  return { small, big };
}

export function hasBoxes(counts: BoxCounts): boolean {
  return counts.small > 0 || counts.big > 0;
}

const LOCALES: Record<Language, string> = { fr: "fr-TN", ar: "ar-TN" };

/** A box count: an integer, no unit and no decimals (formatQuantity would add "kg" and 3 decimals). */
export function formatBoxCount(count: number, language: Language = currentLanguage()): string {
  if (!Number.isSafeInteger(count)) throw new TypeError(`Not a box count: ${JSON.stringify(count)}`);
  return new Intl.NumberFormat(LOCALES[language], { maximumFractionDigits: 0 }).format(count);
}
