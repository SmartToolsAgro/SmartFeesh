import type { StockMovementKindEnum } from "@frutti/api";

export const MOVEMENT_KINDS: StockMovementKindEnum[] = [
  "receipt",
  "transfer",
  "sale",
  "customer_return",
  "supplier_return",
  "loss",
  "adjustment",
  "count_correction",
];

/** The prototype's colours: receipts green, transfers blue, sales coral, losses red. */
export const MOVEMENT_TONES = {
  receipt: "good",
  transfer: "sea",
  sale: "coral",
  customer_return: "neutral",
  supplier_return: "neutral",
  loss: "bad",
  adjustment: "warn",
  count_correction: "warn",
} as const satisfies Record<StockMovementKindEnum, string>;
