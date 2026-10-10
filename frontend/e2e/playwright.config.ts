import { defineConfig, devices } from "@playwright/test";

// End-to-end tests for the critical flows. `pnpm e2e` starts the backend and both apps itself;
// it needs PostgreSQL at DATABASE_URL (see .env.example) and creates the dev logins with `seed_dev`.
const ADMIN_URL = "http://localhost:5173";
const TRUCK_URL = "http://localhost:5174";
const API_URL = "http://localhost:8000";

const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  reporter: isCI ? [["github"], ["list"]] : "list",
  use: { trace: "retain-on-failure", locale: "fr-FR" },
  projects: [
    { name: "admin", testMatch: /admin\..*\.spec\.ts/, use: { ...devices["Desktop Chrome"], baseURL: ADMIN_URL } },
    { name: "truck", testMatch: /truck\..*\.spec\.ts/, use: { ...devices["Pixel 7"], baseURL: TRUCK_URL } },
  ],
  webServer: [
    {
      command:
        "uv run python manage.py migrate --noinput && uv run python manage.py seed_dev && uv run python manage.py runserver localhost:8000 --noreload",
      cwd: "../../backend",
      url: `${API_URL}/api/v1/health`,
      env: { DJANGO_SETTINGS_MODULE: "config.settings.dev" },
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
    {
      command: "pnpm --filter @frutti/admin dev",
      cwd: "..",
      url: ADMIN_URL,
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
    {
      command: "pnpm --filter @frutti/truck dev",
      cwd: "..",
      url: TRUCK_URL,
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
  ],
});
