import type { Customer } from "@frutti/api";

import type { BoxCountInputs } from "../boxes/shared";

/** One product line of a transfer form, as typed. */
export type Line = {
  key: number;
  product: string;
  quantity: string;
  unit_price: string;
  // Once a person types a price, the form stops showing the price in force.
  priceTouched: boolean;
};

/** The part of a truck load that is for one client: their products, boxes and the address of their BL (D-160). */
export type Part = {
  key: number;
  customer: string;
  address: string;
  lines: Line[];
  boxes: BoxCountInputs;
};

// Gives each line and part a stable React key, also for those not saved yet.
let nextKey = 0;

export function newLine(fields: Partial<Line> = {}): Line {
  nextKey += 1;
  return { key: nextKey, product: "", quantity: "", unit_price: "", priceTouched: false, ...fields };
}

export function newPart(fields: Partial<Part> = {}): Part {
  nextKey += 1;
  return { key: nextKey, customer: "", address: "", lines: [newLine()], boxes: { small: "", big: "" }, ...fields };
}

// The API writes "20.250"; people here write "20,250". Both are read back by parseDecimalInput.
export const asTyped = (value: string) => value.replace(".", ",");

/** Errors of a line are reported on `lines.<index>.<field>`, under `deliveries.<i>.` for a client's part. */
export const lineKey = (index: number, field: string) => `lines.${index}.${field}`;

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
