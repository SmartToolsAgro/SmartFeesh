// Minimal API helper for the session endpoints. Business endpoints will use the generated client
// from packages/api (P0-T09), which can reuse `apiFetch` as its transport.

const API_ROOT = "/api/v1";
const CSRF_COOKIE = "csrftoken";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
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
  // The cookie is set by the server (session auth, D-008); ask for it once if it is not there yet.
  if (readCookie(CSRF_COOKIE) === null) await fetch(`${API_ROOT}/auth/csrf`, { credentials: "same-origin" });
  return readCookie(CSRF_COOKIE) ?? "";
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return `Erreur ${response.status}`;
}

export async function apiFetch<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (!SAFE_METHODS.has(method)) headers["X-CSRFToken"] = await csrfToken();

  const response = await fetch(`${API_ROOT}${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });

  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
