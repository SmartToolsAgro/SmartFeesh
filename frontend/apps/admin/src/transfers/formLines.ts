import type { Customer } from "@frutti/api";

import type { BoxCountInputs } from "../boxes/shared";
import { type Line, withSpare } from "../lib/lines";

/** The part of a truck load that is for one client: their products, boxes and the address of their BL (D-160). */
export type Part = {
  key: number;
  customer: string;
  address: string;
  /** Typed in a grid like a sale's (`LinesGrid`, D-174), ending with a blank row. */
  lines: Line[];
  boxes: BoxCountInputs;
};

// Gives each part a stable React key, also for those not saved yet.
let nextKey = 0;

export function newPart(fields: Partial<Part> = {}): Part {
  nextKey += 1;
  return { key: nextKey, customer: "", address: "", lines: withSpare([]), boxes: { small: "", big: "" }, ...fields };
}

/** The address a BL starts from: the client's own, which the person may change for this BL only. */
export function addressOf(customer: Pick<Customer, "address" | "city"> | undefined): string {
  return customer ? [customer.address, customer.city].filter(Boolean).join(", ") : "";
}

/** The errors under one prefix (`deliveries.0.`), with the prefix taken off, for a field made to read plain keys. */
export function scopedErrors(errors: Record<string, string>, prefix: string): Record<string, string> {
  const scoped: Record<string, string> = {};
  for (const [key, message] of Object.entries(errors)) {
    if (key.startsWith(prefix)) scoped[key.slice(prefix.length)] = message;
  }
  return scoped;
}
