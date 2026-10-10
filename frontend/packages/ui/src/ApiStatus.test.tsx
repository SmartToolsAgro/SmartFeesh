import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ApiStatus } from "./ApiStatus";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("shows that the server is connected when the health check answers", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(null, { status: 200 }))),
  );

  render(<ApiStatus />);

  expect(screen.getByRole("status").dataset.status).toBe("checking");
  expect((await screen.findByText("Serveur connecté")).dataset.status).toBe("ok");
});

test("shows that the server is unreachable when the request fails", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new TypeError("network down"))),
  );

  render(<ApiStatus />);

  expect((await screen.findByText("Serveur injoignable")).dataset.status).toBe("down");
});
