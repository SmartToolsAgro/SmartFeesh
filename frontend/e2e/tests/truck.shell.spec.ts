import { expect, type Page, test } from "@playwright/test";

async function logIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Identifiant").fill("driver");
  await page.getByLabel("Mot de passe").fill("frutti-dev");
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page.getByRole("heading", { name: "Bonjour Sami" })).toBeVisible();
}

test("the bottom bar has the four tabs of the prototype and switches screen", async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: "light" });
  await logIn(page);
  const tabs = page.getByRole("navigation", { name: "Navigation camion" });

  await expect(tabs.getByRole("link")).toHaveText(["Ma journée", "Mon stock", "Vente", "Clôture"]);
  await expect(tabs.getByRole("link", { name: "Ma journée" })).toHaveAttribute("aria-current", "page");
  await page.screenshot({ path: testInfo.outputPath("truck-light.png") });

  await tabs.getByRole("link", { name: "Vente" }).click();

  await expect(page).toHaveURL(/\/vente$/);
  await expect(page.getByRole("heading", { name: "Pour quel client ?" })).toBeVisible();
  await expect(tabs.getByRole("link", { name: "Vente" })).toHaveAttribute("aria-current", "page");
});

test("the driver app follows a dark device", async ({ page }, testInfo) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await logIn(page);

  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(7, 26, 35)");
  await page.screenshot({ path: testInfo.outputPath("truck-dark.png") });
});
