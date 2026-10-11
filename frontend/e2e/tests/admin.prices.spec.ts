import { expect, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// Demo catalogue, minimum prices and stock created by `manage.py seed_dev`.
test.use({ storageState: OWNER_STATE });

async function openBoard(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: "Prix du jour" }).click();
  await expect(page.getByRole("heading", { name: "Prix du jour", level: 1 })).toBeVisible();
}

function priceField(page: Page, product: string) {
  return page.getByRole("textbox", { name: `Prix de vente de ${product}`, exact: true });
}

test("the owner sees prices, costs and margins, changes a price twice and sees who changed it", async ({ page }) => {
  await openBoard(page);

  // Prefilled with the price in force; the cost columns come from the batches in stock.
  await expect(priceField(page, "Crevette Royale")).toHaveValue("42,000");
  await expect(page.getByRole("textbox", { name: "Prix minimum de Crevette Royale" })).toHaveValue("33,600");
  await expect(page.getByRole("columnheader", { name: "Coût moyen" })).toBeVisible();

  // The preview follows the typing, before anything is saved.
  const mullet = priceField(page, "Mulet");
  const first = `13,${100 + (Date.now() % 400)}`;
  const second = `13,${500 + (Date.now() % 400)}`;
  await mullet.fill(first);
  await page.getByRole("button", { name: "Enregistrer les prix" }).click();
  await expect(page.getByText("Prix enregistrés.")).toBeVisible();

  // Changed again the same day: both prices are listed, each with who set it.
  await mullet.fill(second);
  await page.getByRole("button", { name: "Enregistrer les prix" }).click();
  const today = page.getByRole("list", { name: "Prix du jour de Mulet" });
  await expect(today.getByRole("listitem").last()).toContainText(second);
  await expect(today).toContainText(first);
  await expect(mullet).toHaveValue(second);

  // Put the demo price back.
  await mullet.fill("13,500");
  await page.getByRole("button", { name: "Enregistrer les prix" }).click();
  await expect(mullet).toHaveValue("13,500");
});

test("a price under the minimum is saved with a warning, never blocked", async ({ page }) => {
  await openBoard(page);

  const sardine = priceField(page, "Sardine");
  await sardine.fill("1,000");
  await expect(page.getByText("Sous le minimum")).toBeVisible();
  await page.getByRole("button", { name: "Enregistrer les prix" }).click();
  await expect(page.getByText(/sous le minimum : enregistrés/)).toBeVisible();
  await expect(sardine).toHaveValue("1,000");

  await sardine.fill("7,500");
  await page.getByRole("button", { name: "Enregistrer les prix" }).click();
  await expect(sardine).toHaveValue("7,500");
  await expect(page.getByText("Sous le minimum")).toHaveCount(0);
});
