import { expect, type Page, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// Demo trucks and driver Sami B. come from `manage.py seed_dev`. The development database is kept between
// runs, so each run uses a day of its own, far in the future.
test.use({ storageState: OWNER_STATE });

async function openDay(page: Page, date: string) {
  await page.goto("/");
  await page.getByRole("link", { name: "Stock frigo & camions" }).click();
  await expect(page.getByRole("heading", { name: "Camions du jour" })).toBeVisible();
  await page.getByLabel("Jour", { exact: true }).fill(date);
}

const driverOf = (page: Page, truck: string) => page.getByRole("combobox", { name: `Chauffeur de ${truck}` });

test("the owner gives a truck to a driver for a day, sees the refusal of a second one, and removes it", async ({
  page,
}) => {
  const day = new Date(Date.UTC(2040, 0, 1) + (Date.now() % 3000) * 86_400_000).toISOString().slice(0, 10);
  await openDay(page, day);

  // Nothing is assigned that day: Camion 1 shows its usual driver as the default.
  await expect(driverOf(page, "Camion 1")).toContainText("Habituel : Sami B.");

  await driverOf(page, "Camion 2").click();
  await page.getByRole("option", { name: "Sami B." }).click();
  await expect(page.getByText("Chauffeur enregistré.")).toBeVisible();
  await expect(driverOf(page, "Camion 2")).toContainText("Sami B.");

  // One truck per driver and day: the server says where Sami already is.
  await driverOf(page, "Camion 3").click();
  await page.getByRole("option", { name: "Sami B. (sur Camion 2)" }).click();
  await expect(page.getByRole("alert")).toContainText("Sami B. conduit déjà Camion 2");
  await expect(driverOf(page, "Camion 3")).toContainText("Aucun chauffeur");

  // Another day is not affected.
  await page.getByLabel("Jour", { exact: true }).fill("2039-12-31");
  await expect(driverOf(page, "Camion 2")).toContainText("Aucun chauffeur");
  await page.getByLabel("Jour", { exact: true }).fill(day);

  await driverOf(page, "Camion 2").click();
  await page.getByRole("option", { name: "Aucun chauffeur" }).click();
  await expect(page.getByText("Attribution retirée.")).toBeVisible();
  await expect(driverOf(page, "Camion 2")).toContainText("Aucun chauffeur");
});
