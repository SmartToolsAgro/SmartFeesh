/**
 * Error reporting of both apps to Sentry (P4-T04, D-140). Off unless the app was built with a DSN
 * (`VITE_SENTRY_DSN`): without one nothing is set up and nothing leaves the browser.
 *
 * What is sent: the error, the app name, the release, the page path and the user's id. Never a name, an
 * e-mail, an address or the query string of a page or a request (searches can hold a customer's name).
 */
import * as Sentry from "@sentry/react";

export type AppName = "admin" | "truck";

/** The build-time settings, as Vite gives them in `import.meta.env`. */
export interface MonitoringEnv {
  VITE_SENTRY_DSN?: string;
  VITE_SENTRY_ENVIRONMENT?: string;
  VITE_RELEASE?: string;
}

let enabled = false;

function withoutQuery(url: unknown): unknown {
  return typeof url === "string" ? url.split(/[?#]/, 1)[0] : url;
}

function scrubEvent<E extends Sentry.Event>(event: E): E {
  if (event.request) {
    event.request.url = withoutQuery(event.request.url) as string | undefined;
    delete event.request.query_string;
    delete event.request.cookies;
  }
  return event;
}

function scrubBreadcrumb(breadcrumb: Sentry.Breadcrumb): Sentry.Breadcrumb | null {
  // What the app writes to the console may quote a server answer: keep it out.
  if (breadcrumb.category === "console") return null;
  if (breadcrumb.data) {
    for (const key of ["url", "from", "to"]) {
      if (key in breadcrumb.data) breadcrumb.data[key] = withoutQuery(breadcrumb.data[key]);
    }
  }
  return breadcrumb;
}

/** Starts the error reporting when the build has a DSN. Returns whether it did. */
export function initMonitoring(app: AppName, env: MonitoringEnv): boolean {
  const dsn = env.VITE_SENTRY_DSN?.trim();
  if (!dsn) return false;
  Sentry.init({
    dsn,
    release: env.VITE_RELEASE?.trim() || undefined,
    environment: env.VITE_SENTRY_ENVIRONMENT?.trim() || "production",
    sendDefaultPii: false,
    initialScope: { tags: { app } },
    beforeSend: scrubEvent,
    beforeBreadcrumb: scrubBreadcrumb,
  });
  enabled = true;
  return true;
}

/** Whether errors are being reported (a DSN was given at build time). */
export function monitoringEnabled(): boolean {
  return enabled;
}

/** Ties the next reports to the logged-in user, by id only; `null` after a logout. */
export function setMonitoringUser(id: number | null): void {
  if (!enabled) return;
  Sentry.setUser(id === null ? null : { id: String(id) });
}

/**
 * React's root error callbacks: errors caught by an error boundary (a route's error screen) and uncaught
 * ones are reported too. React's own console messages are kept. Without a DSN they only log.
 */
export const reactErrorHandlers = {
  onCaughtError: Sentry.reactErrorHandler((error, errorInfo) => console.error(error, errorInfo.componentStack)),
  onUncaughtError: Sentry.reactErrorHandler((error, errorInfo) => console.error(error, errorInfo.componentStack)),
};
