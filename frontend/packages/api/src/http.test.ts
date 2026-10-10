import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError, apiFetch, getSession, login, schemas } from "./index";

interface Call {
  url: string;
  method: string;
  csrf: string | null;
  credentials: RequestCredentials | undefined;
}

function json(status: number, body: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

/** Records every request and answers with `answer`, except the CSRF endpoint, which sets the cookie. */
function stubServer(answer: () => Response): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init: RequestInit = {}) => {
      calls.push({
        url,
        method: init.method ?? "GET",
        csrf: new Headers(init.headers).get("X-CSRFToken"),
        credentials: init.credentials,
      });
      if (url === "/api/v1/auth/csrf") {
        document.cookie = "csrftoken=token-from-server";
        return Promise.resolve(json(204, undefined));
      }
      return Promise.resolve(answer());
    }),
  );
  return calls;
}

beforeEach(() => {
  document.cookie = "csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

afterEach(() => vi.unstubAllGlobals());

test("a read sends the session cookie and no CSRF token", async () => {
  const calls = stubServer(() => json(200, { ok: true }));

  expect(await apiFetch("/api/v1/health")).toEqual({ ok: true });

  expect(calls).toEqual([{ url: "/api/v1/health", method: "GET", csrf: null, credentials: "same-origin" }]);
});

test("the first write asks for the CSRF cookie once, then every write carries the token", async () => {
  const calls = stubServer(() => json(204, undefined));

  await apiFetch("/api/v1/auth/logout", { method: "POST" });
  await apiFetch("/api/v1/auth/logout", { method: "POST" });

  expect(calls.map((call) => call.url)).toEqual(["/api/v1/auth/csrf", "/api/v1/auth/logout", "/api/v1/auth/logout"]);
  expect(calls.slice(1).map((call) => call.csrf)).toEqual(["token-from-server", "token-from-server"]);
});

test("an empty answer gives undefined", async () => {
  stubServer(() => json(204, undefined));

  expect(await apiFetch("/api/v1/auth/logout", { method: "POST" })).toBeUndefined();
});

test("a refused request throws an ApiError with the status, the server's message and its details", async () => {
  stubServer(() => json(401, { detail: "Identifiant ou mot de passe incorrect." }));
  const refused = await login({ username: "owner", password: "wrong" }).catch((error: unknown) => error);
  expect(refused).toBeInstanceOf(ApiError);
  expect(refused).toMatchObject({ status: 401, message: "Identifiant ou mot de passe incorrect." });

  stubServer(() => json(400, { language: ["« de » n'est pas un choix valide."] }));
  const invalid = await apiFetch("/api/v1/me", { method: "PATCH" }).catch((error: unknown) => error);
  expect(invalid).toMatchObject({ status: 400, message: "Erreur 400", body: { language: [expect.any(String)] } });
});

test("generated functions call the right address and return the data itself", async () => {
  const session = {
    user: { id: 1, username: "owner", first_name: "Nadia", last_name: "K.", language: "fr" },
    organization: { id: 1, name: "Frutti Del Mare" },
    role: "owner",
    truck: null,
  };
  const calls = stubServer(() => json(200, session));

  expect(await getSession()).toEqual(session);
  expect(calls[0]?.url).toBe("/api/v1/me");
});

test("the generated Zod schemas describe the contract", () => {
  expect(schemas.LoginBody.safeParse({ username: "owner", password: "secret" }).success).toBe(true);
  expect(schemas.LoginBody.safeParse({ username: "owner" }).success).toBe(false);
  expect(schemas.SetLanguageBody.safeParse({ language: "ar" }).success).toBe(true);
  expect(schemas.SetLanguageBody.safeParse({ language: "de" }).success).toBe(false);
});
