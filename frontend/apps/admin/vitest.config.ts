import { defineConfig } from "vitest/config";

// Unit tests of the admin app's own helpers; screens are covered by the Playwright tests (frontend/e2e).
export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
