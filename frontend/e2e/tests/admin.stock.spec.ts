import { expect, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// Demo data from `manage.py seed_dev`: cold rooms and trucks holding the demo batches. Dorade royale comes
// from two suppliers at 20,000 and 18,500 DT/kg (Q4), so its average purchase price lies between the two.
// These tests only read stock.
test.use({ storageState: OWNER_STATE });

test("the stock page shows each place with its kilos and each product with its purchase prices", async ({ page }) => {
  await page.goto("/stock");

  await expect(page.getByRole("heading", { name: "Stock frigo & camions", level: 1 })).toBeVisible();
  // A cold room card: kilos and cost on a line of their own.
  await expect(page.getByRole("article", { name: "Chambre froide 1 (frais)" })).toContainText(/\d.* kg · .* DT/);

  const dorade = page.getByRole("article", { name: "Dorade royale" });
  await expect(dorade.getByTestId("average-cost")).toContainText(/^(18|19|20),\d{3}/);
  await expect(dorade.getByTestId("last-cost")).toContainText(/(18|20),\d{3}/);
  // The low-stock badge is either one or the other, never missing.
  await expect(dorade.getByText(/^(OK|Sous le seuil)$/)).toBeVisible();
});

test("a product opens its batches, and a batch opens its movements", async ({ page }) => {
  await page.goto("/stock");
  await page.getByRole("article", { name: "Dorade royale" }).getByRole("link", { name: "Dorade royale" }).click();

  await expect(page.getByRole("heading", { name: "Stock de Dorade royale", level: 1 })).toBeVisible();
  const summary = page.getByRole("region", { name: "Résumé" });
  await expect(summary.getByTestId("average-cost")).toContainText(/^(18|19|20),\d{3}/);
  await expect(page.getByRole("heading", { name: "Lots en stock" })).toBeVisible();

  const firstBatch = page
    .getByRole("table")
    .first()
    .getByRole("link", { name: /^L-\d+$/ })
    .first();
  const number = (await firstBatch.textContent()) ?? "";
  await firstBatch.click();

  await expect(page.getByRole("heading", { name: `Lot ${number}`, level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Historique du lot" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Réception" }).first()).toBeVisible();
});

test("the movement list filters by type and keeps the other types out", async ({ page }) => {
  await page.goto("/stock/mouvements");
  await expect(page.getByRole("heading", { name: "Mouvements de stock", level: 1 })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Réception" }).first()).toBeVisible();

  await page.getByLabel("Type").selectOption("receipt");
  await expect(page.getByRole("cell", { name: "Transfert" })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Réception" }).first()).toBeVisible();

  // A day far in the past matches nothing.
  await page.getByLabel("Au").fill("2000-01-01");
  await expect(page.getByText("Aucun mouvement ne correspond à ces filtres.")).toBeVisible();
  await page.getByRole("button", { name: "Effacer les filtres" }).click();
  await expect(page.getByRole("cell", { name: "Réception" }).first()).toBeVisible();
});
