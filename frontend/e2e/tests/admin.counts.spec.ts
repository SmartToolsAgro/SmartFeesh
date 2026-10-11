import { expect, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo count INV-0001 of "Chambre froide 2 (congelé)" comes from `manage.py seed_dev`, still open.
test.use({ storageState: OWNER_STATE });

async function openCounts(page: Page) {
  await page.goto("/stock");
  await page.getByRole("navigation", { name: "Rubriques du stock" }).getByRole("link", { name: "Inventaires" }).click();
  await expect(page.getByRole("heading", { name: "Inventaires", level: 1 })).toBeVisible();
}

/** "12,500" → "12,000": a weight typed the French way, minus (or plus) half a kilo. */
function shifted(typed: string, change: number): string {
  const thousandths = Math.round(Number(typed.replace(",", ".")) * 1000) + change * 1000;
  return (thousandths / 1000).toFixed(3).replace(".", ",");
}

test("an open sheet cannot be approved while lines are left to count", async ({ page }) => {
  await openCounts(page);
  await page
    .getByRole("row", { name: /Chambre froide 2 \(congelé\)/ })
    .getByRole("link")
    .first()
    .click();

  await expect(page.getByText("En cours", { exact: true })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("Pesez chaque lot");
  await page.getByRole("button", { name: "Valider l'inventaire" }).click();

  await expect(page.getByText(/Il reste \d+ ligne\(s\) à compter/)).toBeVisible();
  await expect(page.getByText("En cours", { exact: true })).toBeVisible();
});

test("the owner counts Camion 1: each difference becomes a stock correction", async ({ page }) => {
  test.slow(); // a sheet filled line by line, then approved
  await openCounts(page);
  await page.getByRole("button", { name: "Nouvel inventaire" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Emplacement" }).click();
  await page.getByRole("option", { name: "Camion 1", exact: true }).click();
  await dialog.getByRole("button", { name: "Créer la feuille" }).click();

  await expect(page.getByText(/Feuille INV-\d+ créée/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /^INV-\d+$/, level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Reporter l'enregistré" }).click();
  const inputs = page.getByRole("textbox", { name: /Poids compté de/ });
  await expect(inputs.first()).not.toHaveValue("");
  // Half a kilo less in the first batch, half a kilo more in the second: the stock of the truck stays the same.
  const first = await inputs.nth(0).inputValue();
  const second = await inputs.nth(1).inputValue();
  await inputs.nth(0).fill(shifted(first, -0.5));
  await inputs.nth(1).fill(shifted(second, 0.5));
  await expect(page.getByRole("row").nth(1)).toContainText(/[-−]0,500\skg/);
  await page.getByRole("button", { name: "Valider l'inventaire" }).click();

  await expect(page.getByText(/Inventaire INV-\d+ validé : les écarts ont été corrigés/)).toBeVisible();
  await expect(page.getByText("Validé", { exact: true })).toBeVisible();
  await expect(page.getByRole("row").nth(1)).toContainText(/[-−]0,500\skg/);
  await expect(page.getByRole("row").nth(2)).toContainText(/\+0,500\skg/);
  await expect(page.getByRole("button", { name: "Valider l'inventaire" })).toHaveCount(0);
});
