import { expect, type Locator, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo expenses come from `manage.py seed_dev`: DP-0001 (85 DT of fuel for Camion 2's day, approved,
// split over the lots of its morning load), DP-0002 (transport typed on a shrimp lot), DP-0003 (rent, a
// draft), DP-0004 (the accountant, waiting for approval), DP-0005 (ice, refused).
test.use({ storageState: OWNER_STATE });

// A 1 × 1 PNG: enough for the server to read, turn and store as WebP.
const PHOTO = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

async function openExpenses(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: "Charges", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dépenses", level: 1 })).toBeVisible();
}

async function choose(page: Page, scope: Page | Locator, label: string, option: string) {
  await scope.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("Camion 2's fuel of the day is split over the lots it loaded, to the millime", async ({ page }) => {
  await openExpenses(page);
  await page.getByRole("searchbox").fill("Gasoil");

  await page.getByRole("link", { name: /^DP-\d{4}-0001$/ }).click();

  await expect(page.getByRole("heading", { name: /^DP-\d{4}-0001$/, level: 1 })).toBeVisible();
  await expect(page.getByText("Approuvée", { exact: true })).toBeVisible();
  await expect(page.getByText(/Frais du jour de Camion 2/)).toBeVisible();
  const split = page.getByRole("table");
  await expect(split.getByRole("row", { name: /L-\d+/ })).toHaveCount(2);
  await expect(split.getByRole("row", { name: /Total/ })).toContainText(/85,000\sDT/);
});

test("the owner records an expense with a receipt and approves it at once", async ({ page }) => {
  test.slow(); // a form, a photo upload and the expense page
  await openExpenses(page);
  await page.getByRole("button", { name: "Nouvelle dépense" }).click();
  await expect(page.getByRole("heading", { name: "Nouvelle dépense", level: 1 })).toBeVisible();

  await choose(page, page, "Catégorie", "Divers");
  await page.getByLabel("Montant (DT)").fill("12,5");
  await page.getByLabel("Libellé").fill("Sacs poubelle");
  await page.getByLabel("Payé à").fill("Droguerie du port");
  await page
    .getByLabel("Justificatif (photo ou PDF, facultatif)")
    .setInputFiles({ name: "ticket.png", mimeType: "image/png", buffer: PHOTO });
  await page.getByRole("button", { name: "Enregistrer et approuver" }).click();

  await expect(page.getByText(/Dépense DP-\d{4}-\d+ enregistrée et approuvée/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /^DP-\d{4}-\d+$/, level: 1 })).toBeVisible();
  await expect(page.getByText("Approuvée", { exact: true })).toBeVisible();
  await expect(page.getByText(/12,500\sDT/).first()).toBeVisible();
  await expect(page.getByText("Charge générale")).toBeVisible();
  await expect(page.getByRole("img", { name: /Justificatif de la dépense DP-\d{4}-\d+/ })).toBeVisible();
  await expect(page.getByText(/ne se modifie plus/)).toBeVisible();
});

test("an expense waiting for approval can only be refused with a reason", async ({ page }) => {
  await openExpenses(page);
  await page.getByRole("group", { name: "Statut des dépenses" }).getByRole("button", { name: "À approuver" }).click();
  await page.getByRole("searchbox").fill("comptables");
  await page.getByRole("link", { name: /^DP-\d{4}-0004$/ }).click();

  await expect(page.getByRole("note")).toContainText("En attente d'approbation");
  await page.getByRole("button", { name: "Refuser", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Refuser la dépense" }).click();

  await expect(dialog.getByText("Indiquez pourquoi cette dépense est refusée.")).toBeVisible();
  await dialog.getByRole("button", { name: "Retour" }).click();
  await expect(page.getByText("À approuver", { exact: true })).toBeVisible();
});

test("a cost typed on a lot shows in the lot's costs", async ({ page }) => {
  await openExpenses(page);
  await page.getByRole("searchbox").fill("Transport port");
  await page.getByRole("link", { name: /^DP-\d{4}-0002$/ }).click();

  await page.getByRole("link", { name: /^Lot L-\d+ · Crevette Royale$/ }).click();

  const costs = page.getByRole("region", { name: "Coûts du lot" });
  await expect(costs.getByRole("row", { name: /Transport/ })).toContainText(/45,000\sDT/);
  await expect(costs.getByText(/Total approuvé/)).toBeVisible();
});
