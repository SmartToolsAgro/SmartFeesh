import { expect, test as setup } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// Logs the owner in once and saves the session: the screen tests reuse it instead of logging in each
// time, which would reach the server's limit of 8 logins a minute per account.
setup("log the owner in", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Identifiant").fill("owner");
  await page.getByLabel("Mot de passe").fill("frutti-dev");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
  await page.context().storageState({ path: OWNER_STATE });
});
