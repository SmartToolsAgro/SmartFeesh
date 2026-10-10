// Transport used by every generated API function (see orval.config.ts). Written by hand.
// Same-origin requests with the session cookie, and the CSRF token on every write (D-008).

const CSRF_COOKIE = "csrftoken";
const CSRF_URL = "/api/v1/auth/csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

/** A refused request. `status` 401 means "not logged in", 403 "not allowed" (D-023). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** The parsed answer of the server, e.g. field errors on a 400. */
    readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | null {
  for (const part of document.cookie.split("; ")) {
    const [key, ...value] = part.split("=");
    if (key === name) return decodeURIComponent(value.join("="));
  }
  return null;
}

async function csrfToken(): Promise<string> {
  // The server sets the cookie; ask for it once if it is not there yet.
  if (readCookie(CSRF_COOKIE) === null) await fetch(CSRF_URL, { credentials: "same-origin" });
  return readCookie(CSRF_COOKIE) ?? "";
}

async function parseBody(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  const text = await response.text();
  if (text === "") return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function messageOf(status: number, body: unknown): string {
  if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
    return body.detail;
  }
  return `Erreur ${status}`;
}

export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (!SAFE_METHODS.has(method)) headers.set("X-CSRFToken", await csrfToken());

  const response = await fetch(url, { ...init, method, headers, credentials: "same-origin" });
  const body = await parseBody(response);

  if (!response.ok) throw new ApiError(response.status, messageOf(response.status, body), body);
  return body as T;
}
