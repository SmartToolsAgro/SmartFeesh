import { expect, test } from "@playwright/test";

// Logins created by `manage.py seed_dev`.
const PASSWORD = "frutti-dev";

test("the driver logs in to the driver app and logs out", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Identifiant").fill("driver");
  await page.getByLabel("Mot de passe").fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();

  await expect(page.getByText("Espace chauffeur · Frutti Del Mare")).toBeVisible();
  await expect(page.getByText("Sami B.")).toBeVisible();

  await page.getByRole("button", { name: "Se déconnecter" }).click();
  await expect(page.getByRole("form", { name: "Connexion" })).toBeVisible();
});

test("the driver app turns the owner away", async ({ page }) => {
  await page.goto("/login");

  await page.getByLabel("Identifiant").fill("owner");
  await page.getByLabel("Mot de passe").fill(PASSWORD);
  await page.getByRole("button", { name: "Se connecter" }).click();

  await expect(page.getByRole("alert")).toContainText("pas un compte chauffeur");
  await expect(page.getByText("Espace chauffeur")).toHaveCount(0);
});
