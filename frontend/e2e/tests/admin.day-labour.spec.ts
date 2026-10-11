import { expect, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo day labour comes from `manage.py seed_dev`: Ali Ben Salah unloading a shrimp lot on the day of the
// seed, Moncef Trabelsi cleaning the day before, two drafts two days before. These tests add their own days.
test.use({ storageState: OWNER_STATE });

/** Today as the screens write it ("11/10/2026"), in Tunisian time. */
function todayLabel(): string {
  return new Intl.DateTimeFormat("fr-TN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Africa/Tunis",
  }).format(new Date());
}

async function openCalendar(page: Page) {
  await page.goto("/charges");
  await page
    .getByRole("navigation", { name: "Rubriques des charges" })
    .getByRole("link", { name: "Calendrier journaliers" })
    .click();
  await expect(page.getByRole("heading", { name: "Calendrier journaliers", level: 1 })).toBeVisible();
}

async function openToday(page: Page) {
  await page.getByRole("button", { name: new RegExp(`^${todayLabel()} : \\d+ journée`) }).click();
  const dialog = page.getByRole("dialog", { name: `Journaliers du ${todayLabel()}` });
  await expect(dialog).toBeVisible();
  return dialog;
}

test("the month shows the demo days; a day opens who worked and on which lot", async ({ page }) => {
  await openCalendar(page);

  const dialog = await openToday(page);

  const ali = dialog.getByRole("listitem").filter({ hasText: "Ali Ben Salah" }).first();
  await expect(ali).toContainText("Chargement, déchargement");
  await expect(ali).toContainText(/Lot L-\d+ · Crevette Royale/);
  await expect(ali).toContainText(/40,000\sDT/);
  await expect(ali).toContainText("Approuvée");
});

test("the owner adds a day on a lot from the calendar, and the lot shows it", async ({ page }) => {
  test.slow(); // the calendar, the dialog, then the lot page
  await openCalendar(page);
  const dialog = await openToday(page);

  await dialog.getByRole("combobox", { name: "Journalier" }).click();
  await page.getByRole("option", { name: "Moncef Trabelsi", exact: true }).click();
  await expect(dialog.getByLabel("Montant payé (DT)")).toHaveValue("35,000");
  await dialog.getByRole("combobox", { name: "Lot" }).click();
  await page
    .getByRole("option", { name: /^L-\d+ · Crevette Royale$/ })
    .first()
    .click();
  await dialog.getByRole("combobox", { name: "Travail" }).click();
  await page.getByRole("option", { name: "Rangement du stock", exact: true }).click();
  await dialog.getByRole("button", { name: "Ajouter et approuver" }).click();

  await expect(page.getByText(/Moncef Trabelsi : 35,000\sDT noté/)).toBeVisible();
  const moncef = dialog
    .getByRole("listitem")
    .filter({ hasText: "Moncef Trabelsi" })
    .filter({ hasText: "Rangement du stock" })
    .last();
  await expect(moncef).toContainText("Approuvée");

  await moncef.getByRole("link", { name: /^Lot L-\d+/ }).click();
  const costs = page.getByRole("region", { name: "Coûts du lot" });
  await expect(costs.getByRole("row", { name: /Moncef Trabelsi/ }).first()).toContainText(/35,000\sDT/);
});

test("the owner adds a day labourer with a usual daily pay", async ({ page }) => {
  await page.goto("/charges/journaliers");
  await expect(page.getByRole("heading", { name: "Journaliers", level: 1 })).toBeVisible();
  const name = `Karim Essai ${Date.now() % 100000}`;

  await page.getByRole("button", { name: "Nouveau journalier" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Nom").fill(name);
  await dialog.getByLabel("Téléphone").fill("55 111 222");
  await dialog.getByLabel("Paie habituelle par jour (DT)").fill("30");
  await dialog.getByRole("button", { name: "Enregistrer" }).click();

  await expect(page.getByRole("row", { name: new RegExp(name) })).toContainText(/30,000\sDT/);
});
