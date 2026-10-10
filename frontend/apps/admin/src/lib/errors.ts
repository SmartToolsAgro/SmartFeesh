import { ApiError } from "@frutti/api";

/** Field messages of a 400 answer, `{ reference: "Un autre produit porte déjà cette référence." }`. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.status !== 400) return {};
  if (typeof error.body !== "object" || error.body === null) return {};
  const errors: Record<string, string> = {};
  for (const [field, messages] of Object.entries(error.body)) {
    if (Array.isArray(messages) && typeof messages[0] === "string") errors[field] = messages[0];
    else if (typeof messages === "string") errors[field] = messages;
  }
  return errors;
}
