import type { BoxBalance, BoxTypeEnum } from "@frutti/api";
import { type Language, currentLanguage } from "@frutti/i18n";

export type HolderKind = "location" | "customer" | "supplier";

export const HOLDER_KINDS: HolderKind[] = ["location", "customer", "supplier"];
export const BOX_TYPES: BoxTypeEnum[] = ["small", "big"];

/** One holder with its small and big counts. A box type the holder never moved counts as 0. */
export interface HolderCounts {
  id: number;
  name: string;
  kind: HolderKind;
  small: number;
  big: number;
}

function isHolderKind(value: string): value is HolderKind {
  return (HOLDER_KINDS as string[]).includes(value);
}

/**
 * Groups the balance rows (one per holder and box type) into one row per holder, sorted by name.
 * Rows of an unknown holder kind are skipped rather than shown under the wrong heading.
 */
export function holdersFromBalances(rows: BoxBalance[]): HolderCounts[] {
  const byId = new Map<number, HolderCounts>();
  for (const row of rows) {
    if (!isHolderKind(row.holder_kind)) continue;
    let holder = byId.get(row.holder_id);
    if (!holder) {
      holder = { id: row.holder_id, name: row.holder_name ?? "", kind: row.holder_kind, small: 0, big: 0 };
      byId.set(row.holder_id, holder);
    }
    holder[row.box_type] = row.count;
  }
  return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name, "fr"));
}

export function holdersOfKind(holders: HolderCounts[], kind: HolderKind): HolderCounts[] {
  return holders.filter((holder) => holder.kind === kind);
}

export interface CustomerBoxCounts {
  small: number;
  big: number;
  /** More than one client holder has this name: the counts cannot be told apart. */
  ambiguous: boolean;
}

/**
 * The boxes a client holds. The balance rows carry the holder's name, not the customer's id, so a
 * client is matched by name. Several holders with the same name are reported as ambiguous.
 */
export function customerBoxCounts(holders: HolderCounts[], customerName: string): CustomerBoxCounts {
  const matches = holders.filter((holder) => holder.kind === "customer" && holder.name === customerName);
  const [first] = matches;
  if (!first) return { small: 0, big: 0, ambiguous: false };
  return { small: first.small, big: first.big, ambiguous: matches.length > 1 };
}

const LOCALES: Record<Language, string> = { fr: "fr-TN", ar: "ar-TN" };

/** A box count: an integer, no unit and no decimals (formatQuantity would add "kg" and 3 decimals). */
export function formatBoxCount(count: number, language: Language = currentLanguage()): string {
  if (!Number.isSafeInteger(count)) throw new TypeError(`Not a box count: ${JSON.stringify(count)}`);
  return new Intl.NumberFormat(LOCALES[language], { maximumFractionDigits: 0 }).format(count);
}
