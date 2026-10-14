/// <reference types="vite/client" />

// Build-time settings (D-140). All optional: empty or missing means Sentry stays off.
interface ImportMetaEnv {
  readonly VITE_SENTRY_DSN?: string;
  readonly VITE_SENTRY_ENVIRONMENT?: string;
  readonly VITE_RELEASE?: string;
}
