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

/** Where the boxes of one type stand, and how many are the company's own (D-187). */
export interface BoxSummary {
  /** In the cold rooms and trucks, whoever owns them. */
  inHand: number;
  /** Left at clients: to collect. */
  atCustomers: number;
  /** Lent by suppliers: to give back. */
  owedToSuppliers: number;
  /** The company's own boxes: in hand + at clients − owed to suppliers. Boxes are alike, so this is a count only. */
  own: number;
}

/**
 * Adds up the holders per kind for each box type. Only buying boxes, a write-off and the opening stock change
 * `own`: a receipt or a return moves a location and a supplier by the same count, and a load, a delivery or a
 * pickup only moves boxes between our places and clients.
 */
export function boxSummary(holders: HolderCounts[]): Record<BoxTypeEnum, BoxSummary> {
  const summaryOf = (boxType: BoxTypeEnum): BoxSummary => {
    const total = (kind: HolderKind) => holdersOfKind(holders, kind).reduce((sum, holder) => sum + holder[boxType], 0);
    const inHand = total("location");
    const atCustomers = total("customer");
    const owedToSuppliers = total("supplier");
    return { inHand, atCustomers, owedToSuppliers, own: inHand + atCustomers - owedToSuppliers };
  };
  return { small: summaryOf("small"), big: summaryOf("big") };
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

/** The box counts as typed in a form: one text per box type, empty for none. */
export type BoxCountInputs = Record<BoxTypeEnum, string>;

export const NO_BOX_INPUTS: BoxCountInputs = { small: "", big: "" };

/**
 * The counts a form sends: the non-zero whole counts by box type. A blank or zero input means none.
 * `invalid` names the box types typed as something other than a whole number of boxes.
 */
export function boxCountsFromInputs(inputs: BoxCountInputs): {
  counts: Record<string, number>;
  invalid: BoxTypeEnum[];
} {
  const counts: Record<string, number> = {};
  const invalid: BoxTypeEnum[] = [];
  for (const boxType of BOX_TYPES) {
    const typed = inputs[boxType].trim();
    if (typed === "") continue;
    const count = /^\d+$/.test(typed) ? Number(typed) : Number.NaN;
    if (!Number.isSafeInteger(count)) invalid.push(boxType);
    else if (count > 0) counts[boxType] = count;
  }
  return { counts, invalid };
}

/** The inputs showing counts already saved (a draft reloaded). Zero shows as an empty input. */
export function boxInputsFromCounts(counts: Partial<Record<string, number>> | undefined): BoxCountInputs {
  return {
    small: counts?.small ? String(counts.small) : "",
    big: counts?.big ? String(counts.big) : "",
  };
}
