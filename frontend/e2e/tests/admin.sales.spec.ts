import { expect, type Locator, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo sales come from `manage.py seed_dev` (D-051). These tests make their own sales from the fresh
// cold room, in products the other tests leave alone (rouget, sardine, poulpe), so they can run in any order.
test.use({ storageState: OWNER_STATE });

const FRESH_ROOM = "Chambre froide 1 (frais)";

async function choose(page: Page, scope: Page | Locator, label: string, option: string) {
  await scope.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("the demo sales are listed with what is still owed", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Ventes & factures" }).click();
  await expect(page.getByRole("heading", { name: "Ventes", level: 1 })).toBeVisible();

  await page.getByRole("searchbox").fill("Corail");
  const row = page.getByRole("row", { name: /Restaurant Le Corail/ });
  await expect(row).toContainText("Confirmée");
  await expect(row).toContainText("Camion 1");

  await row.getByRole("link").click();
  await expect(page.getByRole("heading", { name: /^VE-\d+$/, level: 1 })).toBeVisible();
  await expect(page.getByText(/Espèces · 50,000\sDT/)).toBeVisible();
  // Each line names the lots its kilos came from, with their cost.
  await expect(page.getByRole("list", { name: "Lots" }).first()).toContainText(/Lot L-\d+/);
});

test("a counter sale to the walk-in customer is weighed, paid and confirmed at once", async ({ page }) => {
  test.slow();
  await page.goto("/ventes");
  await page.getByRole("button", { name: "Vente comptoir" }).click();
  await expect(page.getByRole("heading", { name: "Vente comptoir", level: 1 })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Chambre froide" })).toHaveText(FRESH_ROOM);
  await expect(page.getByRole("combobox", { name: "Client" })).toHaveText("Client de passage");

  await choose(page, page, "Produit", "Rouget · RO-009");
  // The daily price is proposed; the cold room's stock is shown.
  await expect(page.getByLabel("Prix (DT/kg)")).toHaveValue("14,000");
  await expect(page.getByText(/En stock à Chambre froide 1 \(frais\)/)).toBeVisible();
  await page.getByLabel("Poids (kg)").fill("1,5");
  await page.getByRole("button", { name: "Ajouter" }).click();

  const basket = page.getByRole("region", { name: "Panier" });
  await expect(basket.getByRole("row", { name: /Rouget/ })).toContainText(/21,000\sDT/);
  await page.getByRole("group", { name: "Payé par" }).getByRole("button", { name: "Carte bancaire" }).click();
  await page.getByRole("button", { name: /Encaisser 21,000\sDT/ }).click();

  await expect(page.getByRole("status")).toContainText(/Vente VE-\d+ encaissée/);
  await expect(basket).toContainText("Ajoutez un produit pesé.");
  await page.getByRole("link", { name: "Voir la vente" }).click();

  await expect(page.getByText("Confirmée", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Client de passage" })).toBeVisible();
  await expect(page.getByText(/Carte bancaire · 21,000\sDT/)).toBeVisible();
  await expect(page.getByRole("region", { name: /^Vente VE-/ })).toContainText(/Reste dû\s*0,000\sDT/);
});

test("a sale is drafted, confirmed, shows on its lot, then is cancelled with a reason", async ({ page }) => {
  test.slow();
  await page.goto("/ventes/nouvelle");
  await choose(page, page, "Client", "Poissonnerie El Bahr · C-003");
  await choose(page, page, "Depuis", FRESH_ROOM);
  const line = page.getByRole("group", { name: "Produit 1" });
  await choose(page, line, "Produit", "Sardine · SA-010");
  await expect(line.getByLabel("Prix (DT/kg)")).toHaveValue("7,500");
  await line.getByLabel("Poids (kg)").fill("4");
  // 4 × 7.500
  await expect(line).toContainText(/30,000\sDT/);
  await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();

  await expect(page.getByText(/Brouillon VE-\d+ enregistré/)).toBeVisible();
  await expect(page.getByRole("note")).toContainText("rien n'est encore sorti du stock");
  const number = (await page.getByRole("heading", { level: 1 }).textContent()) ?? "";

  await page.getByRole("button", { name: "Confirmer la vente" }).click();
  await expect(page.getByText(new RegExp(`Vente ${number} confirmée`))).toBeVisible();
  await expect(page.getByRole("region", { name: /^Vente VE-/ })).toContainText(/Reste dû\s*30,000\sDT/);

  // Drill down to the lot the kilos came from: its sales list this one.
  await page.getByRole("list", { name: "Lots" }).getByRole("link").first().click();
  const lotSales = page.getByRole("region", { name: "Ventes de ce lot" });
  await expect(page.getByRole("heading", { name: "Ventes de ce lot" })).toBeVisible();
  await expect(lotSales.getByRole("link", { name: number })).toBeVisible();
  await lotSales.getByRole("link", { name: number }).click();

  await page.getByRole("button", { name: "Annuler la vente" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("reviennent dans les mêmes lots");
  await dialog.getByRole("button", { name: "Annuler la vente" }).click();
  await expect(dialog.getByText("Indiquez la raison de l'annulation.")).toBeVisible();
  await dialog.getByLabel("Motif").fill("Commande annulée par téléphone");
  await dialog.getByRole("button", { name: "Annuler la vente" }).click();

  await expect(page.getByText(new RegExp(`Vente ${number} annulée`))).toBeVisible();
  await expect(page.getByText("Annulée", { exact: true })).toBeVisible();
  await expect(page.getByText("Commande annulée par téléphone")).toBeVisible();
});

test("a sale asking more than the cold room holds is refused under its line", async ({ page }) => {
  await page.goto("/ventes/nouvelle");
  await choose(page, page, "Client", "Client de passage");
  await choose(page, page, "Depuis", FRESH_ROOM);
  const line = page.getByRole("group", { name: "Produit 1" });
  await choose(page, line, "Produit", "Poulpe · PO-006");
  await line.getByLabel("Poids (kg)").fill("5000");
  await page.getByLabel("Payé en entier").check();
  await choose(page, page, "Mode de paiement", "Espèces");

  await page.getByRole("button", { name: "Enregistrer et confirmer" }).click();

  await expect(line.getByText(/Stock insuffisant/)).toBeVisible();
  await expect(page).toHaveURL(/\/ventes\/nouvelle$/);
});

test("an accepted quote is converted into a sale and the two link to each other", async ({ page }) => {
  test.slow();
  await page.goto("/devis/nouveau");
  await choose(page, page, "Client", "Traiteur Les Saveurs · C-008");
  await choose(page, page, "Stock consulté", FRESH_ROOM);
  const line = page.getByRole("group", { name: "Produit 1" });
  await choose(page, line, "Produit", "Poulpe · PO-006");
  await line.getByLabel("Poids (kg)").fill("2");
  await line.getByLabel("Prix (DT/kg)").fill("30");
  await page.getByRole("button", { name: "Enregistrer et envoyer" }).click();
  await expect(page.getByText(/Devis DV-\d+ enregistré et envoyé/)).toBeVisible();
  await page.getByRole("button", { name: "Accepté par le client" }).click();
  await expect(page.getByText(/Devis DV-\d+ accepté/)).toBeVisible();
  const quoteNumber = (await page.getByRole("heading", { level: 1 }).textContent()) ?? "";

  await page.getByRole("button", { name: "Convertir en vente" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("combobox", { name: "Depuis" })).toHaveText(FRESH_ROOM);
  await dialog.getByRole("button", { name: "Créer et confirmer" }).click();

  await expect(page.getByText(/Vente VE-\d+ créée depuis le devis/)).toBeVisible();
  await expect(page.getByText("Confirmée", { exact: true })).toBeVisible();
  // The quote's price is kept: 2 × 30.000.
  await expect(page.getByRole("row", { name: /Poulpe/ })).toContainText(/60,000\sDT/);
  await page.getByRole("link", { name: quoteNumber }).click();

  await expect(page.getByText("Accepté", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /^VE-\d+$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Convertir en vente" })).toHaveCount(0);
});
