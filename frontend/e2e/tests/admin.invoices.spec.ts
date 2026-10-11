import { expect, type Locator, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo invoices come from `manage.py seed_dev` (D-057): Restaurant Le Corail's is issued, Café-Resto
// Sidi Mansour's is a draft. These tests make their own sale in Sardine (never Seiche: the partnership lot test counts its kilos).
test.use({ storageState: OWNER_STATE });

const FRESH_ROOM = "Chambre froide 1 (frais)";

async function choose(page: Page, scope: Page | Locator, label: string, option: string) {
  await scope.getByRole("combobox", { name: label }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("the issued demo invoice shows VAT, the stamp and a print button", async ({ page }) => {
  await page.goto("/factures");
  await expect(page.getByRole("heading", { name: "Factures", level: 1 })).toBeVisible();
  await page.getByRole("searchbox").fill("Corail");
  const row = page.getByRole("row", { name: /Restaurant Le Corail/ });
  await expect(row).toContainText("Émise");
  await row.getByRole("link", { name: /^FA-\d{4}-\d{4}/ }).click();

  await expect(page.getByRole("heading", { name: /^FA-\d{4}-\d{4}$/, level: 1 })).toBeVisible();
  const totals = page.getByLabel("Totaux");
  await expect(totals).toContainText("Total HT");
  await expect(totals).toContainText("TVA");
  await expect(totals).toContainText(/Timbre fiscal\s*1,000\sDT/);
  await expect(page.getByRole("button", { name: "Imprimer" })).toBeVisible();
  // An issued invoice has no form to change it.
  await expect(page.getByRole("button", { name: "Enregistrer et recalculer" })).toHaveCount(0);
});

test("the finance settings screen shows the rules in force", async ({ page }) => {
  await page.goto("/factures/parametres");
  await expect(page.getByRole("heading", { name: "Paramètres financiers", level: 1 })).toBeVisible();
  await expect(page.getByLabel("TVA par défaut (%)")).toHaveValue("19,00");
  await expect(page.getByLabel("Timbre fiscal (DT par facture)")).toHaveValue("1,000");
  await expect(page.getByLabel("Retenue à la source (%)")).toHaveValue("0,00");
});

test("a sale is invoiced without VAT, then with an edited rate and amount, issued and credited", async ({ page }) => {
  test.slow();
  await page.goto("/ventes/nouvelle");
  await choose(page, page, "Client", "Poissonnerie El Bahr · C-003");
  await choose(page, page, "Depuis", FRESH_ROOM);
  const line = page.getByRole("group", { name: "Produit 1" });
  await choose(page, line, "Produit", "Sardine · SA-010");
  await line.getByLabel("Poids (kg)").fill("2");
  await page.getByRole("button", { name: "Enregistrer le brouillon" }).click();
  await expect(page.getByText(/Brouillon VE-\d+ enregistré/)).toBeVisible();
  await page.getByRole("button", { name: "Confirmer la vente" }).click();
  await expect(page.getByText(/Vente VE-\d+ confirmée/)).toBeVisible();

  await page.getByRole("button", { name: "Facturer" }).click();
  await expect(page.getByRole("heading", { name: "Facture (brouillon)", level: 1 })).toBeVisible();
  const document = page.getByRole("region", { name: /^Facture/ });
  // The company default is proposed: VAT at 19 %.
  await expect(document).toContainText("TVA 19 %");

  // Without VAT: nothing about VAT is shown.
  await page.getByLabel("Facture avec TVA").uncheck();
  await page.getByRole("button", { name: "Enregistrer et recalculer" }).click();
  await expect(page.getByText("Facture enregistrée.")).toBeVisible();
  await expect(document).not.toContainText("TVA");
  await expect(document).not.toContainText("HT");
  await expect(page.getByText("Sans TVA", { exact: true })).toBeVisible();

  // With VAT again, a typed rate of 7 % and a typed amount, both flagged.
  await page.getByLabel("Facture avec TVA").check();
  await page.getByLabel(/^Taux de TVA de Sardine/).fill("7");
  await page.getByRole("button", { name: "Enregistrer et recalculer" }).click();
  await expect(document).toContainText("TVA 7 %");
  await expect(document).toContainText("taux saisi");
  await page.getByLabel("TVA à 7 % (DT)").fill("1,000");
  await page.getByRole("button", { name: "Enregistrer et recalculer" }).click();
  await expect(document).toContainText("montant saisi");

  // Issue: number, then the form is gone and a credit note is the only way to correct.
  await page.getByRole("button", { name: "Émettre la facture" }).click();
  await page.getByRole("button", { name: "Émettre", exact: true }).click();
  await expect(page.getByRole("heading", { name: /^FA-\d{4}-\d{4}$/, level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Enregistrer et recalculer" })).toHaveCount(0);

  await page.getByRole("button", { name: "Faire un avoir" }).click();
  await page.getByLabel("Motif").fill("Erreur de pesée");
  await page.getByRole("button", { name: "Créer l'avoir" }).click();
  await expect(page.getByText(/Avoir AV-\d{4}-\d{4} créé/)).toBeVisible();
  await expect(page.getByText("Annulée", { exact: true })).toBeVisible();
});
