// The same rule as the server (apps/storefront/services.py `normalize_phone`), checked here first so the visitor
// sees the mistake before sending. The server stays the reference.

const SEPARATORS = /[\s.\-/()]/g;

/** "98 123 456" → "+216 98 123 456"; "+33 6 12 34 56 78" → "+33612345678"; anything else → null. */
export function normalizePhone(raw: string): string | null {
  let value = raw.trim().replace(SEPARATORS, "");
  if (value.startsWith("00")) value = `+${value.slice(2)}`;
  if (value.startsWith("+216")) value = value.slice(4);
  if (/^[234579]\d{7}$/.test(value)) return `+216 ${value.slice(0, 2)} ${value.slice(2, 5)} ${value.slice(5)}`;
  if (/^\+\d{8,15}$/.test(value) && !value.startsWith("+216")) return value;
  return null;
}

/** "+216 74 123 456" → "74 123 456": a Tunisian visitor reads the number without the country code. */
export function shownPhone(phone: string): string {
  return phone.startsWith("+216 ") ? phone.slice(5) : phone;
}

/** "+216 74 123 456" → "tel:+21674123456" */
export function telHref(phone: string): string {
  return `tel:${phone.replace(/\s/g, "")}`;
}

/** "+216 98 123 456" → "https://wa.me/21698123456" */
export function whatsappHref(phone: string): string {
  return `https://wa.me/${phone.replace(/\D/g, "")}`;
}
