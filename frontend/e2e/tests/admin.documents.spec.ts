import { expect, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo data of `manage.py seed_dev`: DV-0001 is the prototype's quote to Restaurant Le Corail. Read only:
// the other tests own the demo documents they change.
test.use({ storageState: OWNER_STATE });

test("the documents page lists the demo quote and filters by type", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("navigation", { name: "Modules" }).getByRole("link", { name: "Documents" }).click();
  await expect(page.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();

  await page.getByRole("combobox", { name: "Période" }).click();
  await page.getByRole("option", { name: "Tout", exact: true }).click();
  await page.getByRole("searchbox").fill("Corail");

  const quote = page.getByRole("row", { name: /DV-0001/ });
  await expect(quote).toContainText("Restaurant Le Corail");
  await expect(quote).toContainText("Devis");

  await page.getByRole("button", { name: /^BA/ }).click();
  await expect(page.getByRole("row", { name: /DV-0001/ })).toHaveCount(0);
  await page.getByRole("button", { name: /^DV/ }).click();
  await expect(page.getByRole("row", { name: /DV-0001/ })).toBeVisible();

  await page.getByRole("link", { name: "DV-0001" }).click();
  await expect(page.getByRole("article", { name: "Devis DV-0001" })).toBeVisible();
});

test("a new document starts from the documents page", async ({ page }) => {
  await page.goto("/documents");
  await page.getByRole("button", { name: "Nouveau document" }).click();
  await page.getByRole("button", { name: /Bon de livraison direct/ }).click();

  await expect(page).toHaveURL(/\/ventes\/nouvelle$/);
});
