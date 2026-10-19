// The visitor's basket: product ids and kilos, kept in this browser only. Amounts are decimal strings, computed in
// thousandths with bigint, never JavaScript numbers (ARCHITECTURE §4.1). The server stays the reference.

export type CartLine = { product: number; quantity: string };

const SCALE = 1000n;
const STORAGE_KEY = "frutti-site-cart";
export const MAX_KILOS = "10000";

function toThousandths(value: string): bigint {
  const match = /^(\d+)(?:\.(\d{1,3}))?$/.exec(value);
  if (!match) throw new TypeError(`Not a positive decimal: ${JSON.stringify(value)}`);
  const [, whole = "0", fraction = ""] = match;
  return BigInt(whole) * SCALE + BigInt(fraction.padEnd(3, "0"));
}

function fromThousandths(value: bigint): string {
  return `${value / SCALE}.${(value % SCALE).toString().padStart(3, "0")}`;
}

/** "12,5" or "12.5" → "12.5"; empty, zero, negative, more than 3 decimals or above the maximum → null. */
export function parseKilos(text: string): string | null {
  const value = text.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,3})?$/.test(value)) return null;
  const thousandths = toThousandths(value);
  if (thousandths <= 0n || thousandths > toThousandths(MAX_KILOS)) return null;
  return value;
}

/** Adds kilos of a product: a product already in the basket gets the kilos added, capped at the maximum. */
export function addToCart(lines: readonly CartLine[], product: number, quantity: string): CartLine[] {
  const existing = lines.find((line) => line.product === product);
  if (!existing) return [...lines, { product, quantity }];
  const total = toThousandths(existing.quantity) + toThousandths(quantity);
  const capped = total > toThousandths(MAX_KILOS) ? toThousandths(MAX_KILOS) : total;
  return lines.map((line) => (line.product === product ? { product, quantity: fromThousandths(capped) } : line));
}

export function setQuantity(lines: readonly CartLine[], product: number, quantity: string): CartLine[] {
  return lines.map((line) => (line.product === product ? { product, quantity } : line));
}

export function removeFromCart(lines: readonly CartLine[], product: number): CartLine[] {
  return lines.filter((line) => line.product !== product);
}

/** kilos × web price, rounded half up to the millime like the server's line totals. */
export function lineTotal(quantity: string, price: string): string {
  const product = toThousandths(quantity) * toThousandths(price);
  return fromThousandths((product * 2n + SCALE) / (SCALE * 2n));
}

/** The indicative total of the lines that have a web price; null when none has one. */
export function estimate(lines: readonly CartLine[], prices: ReadonlyMap<number, string | null>): string | null {
  let total = 0n;
  let priced = false;
  for (const line of lines) {
    const price = prices.get(line.product);
    if (!price) continue;
    priced = true;
    total += toThousandths(lineTotal(line.quantity, price));
  }
  return priced ? fromThousandths(total) : null;
}

/** The basket kept in this browser; empty when storage is blocked or holds something unexpected. */
export function loadCart(): CartLine[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (line): line is CartLine =>
        typeof line === "object" &&
        line !== null &&
        typeof (line as CartLine).product === "number" &&
        typeof (line as CartLine).quantity === "string" &&
        parseKilos((line as CartLine).quantity) !== null,
    );
  } catch {
    return [];
  }
}

export function saveCart(lines: readonly CartLine[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
  } catch {
    // Private window or blocked storage: the basket lives until the page closes.
  }
}
