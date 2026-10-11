import { expect, type Locator, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo losses come from `manage.py seed_dev`: PE-0001 (1.5 kg of mussels on Camion 1, under the
// threshold, already out of stock) and PE-0002 (4 kg of rouget, waiting for the owner).
test.use({ storageState: OWNER_STATE });

// A 1 × 1 PNG: enough for the server to read, turn and store as WebP.
const PHOTO = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function openLosses(page: Page) {
  await page.goto("/stock");
  await page.getByRole("navigation", { name: "Rubriques du stock" }).getByRole("link", { name: "Pertes" }).click();
  await expect(page.getByRole("heading", { name: "Pertes", level: 1 })).toBeVisible();
}

async function choose(page: Page, scope: Page | Locator, label: string, option: string) {
  await scope.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("the demo mussels lost on Camion 1 left the stock from their batch, at cost", async ({ page }) => {
  await openLosses(page);
  await expect(page.getByText(/Au-delà de 2,000\skg, une perte attend la validation du propriétaire/)).toBeVisible();
  await page.getByRole("searchbox").fill("Moules");

  await page.getByRole("link", { name: "PE-0001" }).click();

  await expect(page.getByRole("heading", { name: "PE-0001", level: 1 })).toBeVisible();
  await expect(page.getByText("Validée", { exact: true })).toBeVisible();
  await expect(page.getByText("Sac percé pendant la tournée")).toBeVisible();
  await expect(page.getByRole("row", { name: /L-\d+/ })).toContainText(/1,500\skg/);
  await expect(page.getByText("Valeur au coût d'achat")).toBeVisible();
});

test("a loss waiting for the owner can only be refused with a reason", async ({ page }) => {
  await openLosses(page);
  await page.getByRole("group", { name: "Statut des pertes" }).getByRole("button", { name: "En attente" }).click();
  await page.getByRole("searchbox").fill("Rouget");
  await page
    .getByRole("link", { name: /^PE-\d+$/ })
    .first()
    .click();

  await expect(page.getByRole("note")).toContainText("le stock n'a pas encore bougé");
  await expect(page.getByRole("button", { name: "Valider la perte" })).toBeVisible();
  await page.getByRole("button", { name: "Refuser" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Refuser la perte" }).click();

  await expect(dialog.getByText("Indiquez pourquoi la perte est refusée.")).toBeVisible();
  await dialog.getByRole("button", { name: "Retour" }).click();
  await expect(page.getByText("En attente", { exact: true })).toBeVisible();
});

test("the owner declares a loss with a photo: it leaves the stock at once", async ({ page }) => {
  test.slow(); // a form, a photo upload and the loss page
  await openLosses(page);
  await page.getByRole("button", { name: "Déclarer une perte" }).click();
  await expect(page.getByRole("heading", { name: "Déclarer une perte", level: 1 })).toBeVisible();

  await choose(page, page, "Emplacement", "Camion 1");
  await choose(page, page, "Produit", "Crevette Royale · CR-001");
  await expect(page.getByText(/Au stock ici : [\d\s,]+kg/)).toBeVisible();
  await page.getByLabel("Poids perdu (kg)").fill("0,5");
  await choose(page, page, "Raison", "Abîmé ou écrasé");
  await page.getByLabel("Note").fill("Caisse tombée au déchargement");
  await page
    .getByLabel("Photo (facultative)")
    .setInputFiles({ name: "caisse.png", mimeType: "image/png", buffer: PHOTO });
  await page.getByRole("button", { name: "Enregistrer la perte" }).click();

  await expect(page.getByText(/Perte PE-\d+ enregistrée : le stock a été mis à jour/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /^PE-\d+$/, level: 1 })).toBeVisible();
  await expect(page.getByText("Validée", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /Photo de la perte PE-\d+/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /L-\d+/ }).first()).toContainText(/kg/);
});

test("the owner changes the approval threshold", async ({ page }) => {
  await openLosses(page);
  await page.getByRole("button", { name: "Changer le seuil" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Seuil (kg)").fill("2,5");
  await dialog.getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText(/Au-delà de 2,500\skg/)).toBeVisible();

  // Back to the demo value, so the other tests find it.
  await page.getByRole("button", { name: "Changer le seuil" }).click();
  await page.getByRole("dialog").getByLabel("Seuil (kg)").fill("2");
  await page.getByRole("dialog").getByRole("button", { name: "Enregistrer" }).click();
  await expect(page.getByText(/Au-delà de 2,000\skg/)).toBeVisible();
});
