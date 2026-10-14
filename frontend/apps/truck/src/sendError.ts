import { ApiError } from "@frutti/api";

/** The server's refusal as text, or the generic message. */
export function sendError(failure: unknown, fallback: string): string {
  const body = failure instanceof ApiError ? JSON.stringify(failure.body ?? "") : "";
  return body === "" || body === '""' ? fallback : body;
}
