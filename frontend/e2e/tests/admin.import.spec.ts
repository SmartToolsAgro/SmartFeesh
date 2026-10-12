import { expect, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

test.use({ storageState: OWNER_STATE });

test("the owner finds the Excel templates of the data import", async ({ page }) => {
  await page.goto("/import");

  await expect(page.getByRole("heading", { name: "Import de données", level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Modèle Excel : Produits" })).toHaveAttribute(
    "href",
    "/api/v1/imports/products/template",
  );
  await page.getByRole("button", { name: "Clients" }).click();
  await expect(page.getByRole("link", { name: "Modèle Excel : Clients" })).toBeVisible();
  // Nothing to check until a file is chosen.
  await expect(page.getByRole("button", { name: "Vérifier le fichier" })).toBeDisabled();
});
