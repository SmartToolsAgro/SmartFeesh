import { beforeEach, describe, expect, it, vi } from "vitest";

const sentry = vi.hoisted(() => ({
  init: vi.fn(),
  setUser: vi.fn(),
  reactErrorHandler: vi.fn(() => () => undefined),
}));
vi.mock("@sentry/react", () => sentry);

async function freshModule() {
  vi.resetModules();
  return import("./index");
}

describe("monitoring", () => {
  beforeEach(() => {
    sentry.init.mockClear();
    sentry.setUser.mockClear();
  });

  it("stays off and sends nothing without a DSN", async () => {
    const monitoring = await freshModule();

    expect(monitoring.initMonitoring("admin", {})).toBe(false);
    expect(monitoring.initMonitoring("truck", { VITE_SENTRY_DSN: "", VITE_RELEASE: "r1" })).toBe(false);
    expect(monitoring.initMonitoring("truck", { VITE_SENTRY_DSN: "   " })).toBe(false);
    monitoring.setMonitoringUser(7);

    expect(monitoring.monitoringEnabled()).toBe(false);
    expect(sentry.init).not.toHaveBeenCalled();
    expect(sentry.setUser).not.toHaveBeenCalled();
  });

  it("reports with the app name and the release when a DSN is given, and the user by id only", async () => {
    const monitoring = await freshModule();

    const on = monitoring.initMonitoring("truck", {
      VITE_SENTRY_DSN: "https://key@o1.ingest.sentry.io/2",
      VITE_RELEASE: "20261014-abc1234",
      VITE_SENTRY_ENVIRONMENT: "staging",
    });
    monitoring.setMonitoringUser(7);
    monitoring.setMonitoringUser(null);

    expect(on).toBe(true);
    expect(sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: "https://key@o1.ingest.sentry.io/2",
        release: "20261014-abc1234",
        environment: "staging",
        sendDefaultPii: false,
        initialScope: { tags: { app: "truck" } },
      }),
    );
    expect(sentry.setUser.mock.calls).toEqual([[{ id: "7" }], [null]]);
  });

  it("drops query strings and console messages from what it sends", async () => {
    const monitoring = await freshModule();
    monitoring.initMonitoring("admin", { VITE_SENTRY_DSN: "https://key@o1.ingest.sentry.io/2" });
    const options = sentry.init.mock.calls[0]?.[0] as {
      beforeSend: (event: object) => { request: Record<string, unknown> };
      beforeBreadcrumb: (crumb: object) => { data: Record<string, unknown> } | null;
    };

    const event = options.beforeSend({
      request: { url: "https://admin.example/customers?search=Ben%20Ali", query_string: "search=Ben" },
    });
    expect(event.request).toEqual({ url: "https://admin.example/customers" });
    expect(options.beforeBreadcrumb({ category: "console", message: "x" })).toBeNull();
    expect(
      options.beforeBreadcrumb({ category: "fetch", data: { url: "/api/v1/customers?search=Ben", method: "GET" } })
        ?.data,
    ).toEqual({ url: "/api/v1/customers", method: "GET" });
  });
});
