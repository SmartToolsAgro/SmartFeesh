import { expect, test } from "@playwright/test";

import { OWNER_STATE } from "./owner";

// The demo partnership lot comes from `manage.py seed_dev` (apps/demo/partnerships.py): Pêcherie Kerkennah
// shares the seiche lot KRK-1192 (15 kg at 20.500 DT/kg, 40 % of a profit, 25 % of a loss), 4 kg of it
// sold on Sidi Mansour's converted quote, 18.000 DT of transport typed on it, 11 kg still in stock.
// Nothing else in the browser tests touches seiche, and this test only reads.
test.use({ storageState: OWNER_STATE });

test("the partnership lot shows its result so far, step by step, with what lies behind each number", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Partage des bénéfices", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Partenariats", level: 1 })).toBeVisible();
  const row = page.getByRole("row", { name: /Seiche/ });
  await expect(row).toContainText("Pêcherie Kerkennah");
  await expect(row).toContainText(/107,500\sDT/);
  await expect(row).toContainText("40 % / 25 %");

  await row.getByRole("link").click();
  const partnership = page.getByRole("region", { name: "Partenariat" });
  await expect(partnership.getByText("Pêcherie Kerkennah")).toBeVisible();
  await expect(partnership.getByRole("row", { name: /Apport/ })).toContainText(/107,500\sDT/);

  const result = page.getByRole("region", { name: "Résultat du lot" });
  await expect(result.getByText("En cours : résultat à ce jour")).toBeVisible();
  await expect(result.getByText(/^Ventes du lot \(4,000\skg\)/)).toBeVisible();
  // 4 kg × 20.500 DT
  await expect(result.getByText("Coût d'achat des kg vendus").locator("..")).toContainText(/82,000\sDT/);
  // The transport cost opens on the expense behind it.
  await result.getByText("Coûts saisis sur le lot").click();
  await expect(result.getByRole("link", { name: /Transport/ })).toBeVisible();
  // 4 kg sold at Sidi Mansour's price (26.000 DT/kg): 104.000 − 82.000 − 18.000 = 4.000 DT, 40 % of it to
  // the partner (1.600 DT), 2.400 DT to the owner.
  await expect(result.getByText("Résultat net du lot").locator("..")).toContainText(/4,000\sDT/);
  await expect(result.getByText("Part de Pêcherie Kerkennah (40 %)").locator("..")).toContainText(/1,600\sDT/);
  await expect(result.getByText("Part du propriétaire").locator("..")).toContainText(/2,400\sDT/);
  // Not closable yet: 11 kg are still in the cold room, and the screen says so.
  await expect(result.getByText(/Il reste 11,000\skg en stock/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Clôturer le lot" })).toBeDisabled();

  // The sale behind the revenue is one click away.
  await result.getByText(/^Ventes du lot \(4,000\skg\)/).click();
  await result.getByRole("link", { name: /Sidi Mansour/ }).click();
  await expect(page).toHaveURL(/\/ventes\/\d+$/);
});
