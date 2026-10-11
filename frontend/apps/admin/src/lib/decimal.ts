// Sums and products of amounts and weights in the browser, without JavaScript numbers (ARCHITECTURE §4.1):
// a decimal string such as "20.250" becomes 20250n thousandths, and the result goes back to a string.
// The server stays the reference: these only preview what it will compute the same way.

const SCALE = 1000n;

/** "20.25" → 20250n. Throws on anything that is not a plain decimal with at most 3 decimals. */
export function toThousandths(value: string): bigint {
  const match = /^(-?)(\d+)(?:\.(\d{1,3}))?$/.exec(value);
  if (!match) throw new TypeError(`Not a decimal with at most 3 decimals: ${JSON.stringify(value)}`);
  const [, sign, whole = "0", fraction = ""] = match;
  const thousandths = BigInt(whole) * SCALE + BigInt(fraction.padEnd(3, "0"));
  return sign ? -thousandths : thousandths;
}

/** 20250n → "20.250" */
export function fromThousandths(value: bigint): string {
  const negative = value < 0n;
  const absolute = negative ? -value : value;
  const fraction = (absolute % SCALE).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${absolute / SCALE}.${fraction}`;
}

// Divides and rounds half away from zero, like the server's ROUND_HALF_UP.
function divideRounded(numerator: bigint, denominator: bigint): bigint {
  const negative = numerator < 0n !== denominator < 0n;
  const n = numerator < 0n ? -numerator : numerator;
  const d = denominator < 0n ? -denominator : denominator;
  const quotient = (n * 2n + d) / (d * 2n);
  return negative ? -quotient : quotient;
}

/** Quantity × unit price, rounded once to the millime: the server's `line_total`. */
export function lineTotal(quantity: string, unitPrice: string): string {
  return fromThousandths(divideRounded(toThousandths(quantity) * toThousandths(unitPrice), SCALE));
}

/** The sum of decimal strings, exact. */
export function sum(values: readonly string[]): string {
  return fromThousandths(values.reduce((total, value) => total + toThousandths(value), 0n));
}

/** a − b, exact. */
export function subtract(a: string, b: string): string {
  return fromThousandths(toThousandths(a) - toThousandths(b));
}

/** The change from `previous` to `next` in percent with one decimal ("2.5", "-10.0"), or null when
 * `previous` is zero. */
export function percentChange(next: string, previous: string): string | null {
  const before = toThousandths(previous);
  if (before === 0n) return null;
  const tenthsOfPercent = divideRounded((toThousandths(next) - before) * 1000n, before);
  const negative = tenthsOfPercent < 0n;
  const absolute = negative ? -tenthsOfPercent : tenthsOfPercent;
  return `${negative ? "-" : ""}${absolute / 10n}.${absolute % 10n}`;
}
