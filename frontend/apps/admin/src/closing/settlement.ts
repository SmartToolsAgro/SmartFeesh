/** Millimes in a decimal string with at most 3 decimals ("1286.000" -> 1286000n), or null when it is not one. */
function toMillimes(value: string): bigint | null {
  const match = /^(\d+)(?:\.(\d{1,3}))?$/.exec(value);
  if (!match) return null;
  const whole = match[1] ?? "0";
  const decimals = (match[2] ?? "").padEnd(3, "0");
  return BigInt(whole) * 1000n + BigInt(decimals);
}

function fromMillimes(value: bigint): string {
  const sign = value < 0n ? "-" : "";
  const absolute = value < 0n ? -value : value;
  return `${sign}${absolute / 1000n}.${String(absolute % 1000n).padStart(3, "0")}`;
}

/** What is still to type so that the payments add up to the total to pay: "0.000" when they do, positive when
 * short, negative when over; null when a line is not an amount. Exact (millimes, never floats). */
export function remainingToPay(total: string, amounts: string[]): string | null {
  const wanted = toMillimes(total);
  if (wanted === null) return null;
  let paid = 0n;
  for (const amount of amounts) {
    if (amount.trim() === "") continue;
    const parsed = toMillimes(amount.trim());
    if (parsed === null) return null;
    paid += parsed;
  }
  return fromMillimes(wanted - paid);
}
