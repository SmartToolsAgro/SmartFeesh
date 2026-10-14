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

  const quote = page.getByRole("row", { name: /DV-\d{4}-0001/ });
  await expect(quote).toContainText("Restaurant Le Corail");
  await expect(quote).toContainText("Devis");

  await page.getByRole("button", { name: /^BA/ }).click();
  await expect(page.getByRole("row", { name: /DV-\d{4}-0001/ })).toHaveCount(0);
  await page.getByRole("button", { name: /^DV/ }).click();
  await expect(page.getByRole("row", { name: /DV-\d{4}-0001/ })).toBeVisible();

  await page.getByRole("link", { name: /^DV-\d{4}-0001$/ }).click();
  await expect(page.getByRole("article", { name: /^Devis DV-\d{4}-0001$/ })).toBeVisible();
});

test("a new document starts from the documents page", async ({ page }) => {
  await page.goto("/documents");
  await page.getByRole("button", { name: "Nouveau document" }).click();
  await page.getByRole("button", { name: /Bon de livraison direct/ }).click();

  // The form opens in a window over the list; the person stays on Documents (D-137).
  await expect(page.getByRole("dialog", { name: "Bon de livraison direct" })).toBeVisible();
  await expect(page).toHaveURL(/\/documents$/);
});

test("Escape asks before a half-filled document is thrown away", async ({ page }) => {
  await page.goto("/documents");
  await page.getByRole("button", { name: "Nouveau document" }).click();
  await page.getByRole("button", { name: /Devis \(commande client\)/ }).click();
  const form = page.getByRole("dialog", { name: "Devis (commande client)" });
  await expect(form).toBeVisible();

  // Nothing typed yet: Escape closes at once.
  await page.keyboard.press("Escape");
  await expect(form).toBeHidden();

  await page.getByRole("button", { name: "Nouveau document" }).click();
  await page.getByRole("button", { name: /Devis \(commande client\)/ }).click();
  await form.getByLabel("Notes pour le client").fill("Livrer avant midi");
  await page.keyboard.press("Escape");
  const ask = page.getByRole("dialog", { name: "Abandonner ce document ?" });
  await expect(ask).toBeVisible();
  await ask.getByRole("button", { name: "Continuer la saisie" }).click();
  await expect(ask).toBeHidden();
  await expect(form.getByLabel("Notes pour le client")).toHaveValue("Livrer avant midi");

  await page.keyboard.press("Escape");
  await ask.getByRole("button", { name: "Abandonner" }).click();
  await expect(form).toBeHidden();
});
