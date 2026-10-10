import { afterEach, expect, test } from "vitest";

import { applyLanguage, formatDate, formatMoney, formatQuantity, i18n } from "./index";

afterEach(() => applyLanguage("fr"));

test("French is the default language and reads left to right", () => {
  applyLanguage("fr");

  expect(i18n.t("auth.title")).toBe("Connexion");
  expect(document.documentElement.lang).toBe("fr");
  expect(document.documentElement.dir).toBe("ltr");
});

test("Arabic switches the page to right-to-left and falls back to French for missing texts", () => {
  applyLanguage("ar");

  expect(document.documentElement.lang).toBe("ar");
  expect(document.documentElement.dir).toBe("rtl");
  expect(i18n.t("auth.title")).toBe("تسجيل الدخول");
  expect(i18n.t("auth.username")).toBe("Identifiant");
});

test("texts take values", () => {
  expect(i18n.t("admin.dashboard.hello", { name: "Nadia" })).toBe("Bonjour Nadia");
});

test("amounts show three decimals, grouped thousands and the currency", () => {
  expect(formatMoney("1250")).toMatch(/^1\s250,000\sDT$/);
  expect(formatMoney("0.5")).toMatch(/^0,500\sDT$/);
  expect(formatMoney("-42.125")).toMatch(/^-42,125\sDT$/);
  expect(formatMoney("1250", "ar")).toMatch(/^1\.250,000\sد\.ت$/);
});

test("large amounts keep every millime", () => {
  // As a JavaScript number this would lose its last digit.
  expect(formatMoney("99999999999.999")).toMatch(/^99\s999\s999\s999,999\sDT$/);
  expect(formatMoney("9007199254740993.001")).toMatch(/993,001\sDT$/);
});

test("weights show three decimals and the unit", () => {
  expect(formatQuantity("12.5")).toMatch(/^12,500\skg$/);
});

test("numbers that are not decimal strings are refused", () => {
  expect(() => formatMoney("12,5")).toThrow(TypeError);
  expect(() => formatMoney("")).toThrow(TypeError);
  expect(() => formatMoney("1e3")).toThrow(TypeError);
});

test("dates are written day/month/year", () => {
  expect(formatDate("2026-10-09")).toBe("09/10/2026");
  expect(formatDate("2026-01-05")).toBe("05/01/2026");
});

test("a timestamp is shown on its Tunisian date", () => {
  // 23:30 UTC on the 9th is already 00:30 on the 10th in Tunis.
  expect(formatDate("2026-10-09T23:30:00Z")).toBe("10/10/2026");
  expect(() => formatDate("hier")).toThrow(TypeError);
});
