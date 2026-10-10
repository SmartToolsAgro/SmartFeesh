import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { ar } from "./ar";
import { fr, type Translation } from "./fr";

export const LANGUAGES = ["fr", "ar"] as const;
export type Language = (typeof LANGUAGES)[number];

const RIGHT_TO_LEFT: ReadonlySet<Language> = new Set(["ar"]);

declare module "i18next" {
  // Makes `t("auth.title")` checked by the compiler: a wrong key is a type error.
  interface CustomTypeOptions {
    defaultNS: "translation";
    resources: { translation: Translation };
  }
}

// The texts are bundled, so this finishes at once: components can translate on their first render.
void i18n.use(initReactI18next).init({
  resources: { fr: { translation: fr }, ar: { translation: ar } },
  lng: "fr",
  fallbackLng: "fr",
  initAsync: false,
  interpolation: { escapeValue: false }, // React already escapes
});

export function isLanguage(value: unknown): value is Language {
  return LANGUAGES.includes(value as Language);
}

export function currentLanguage(): Language {
  return isLanguage(i18n.language) ? i18n.language : "fr";
}

/** Switches the texts and the reading direction of the whole page. */
export function applyLanguage(language: Language): void {
  void i18n.changeLanguage(language);
  document.documentElement.lang = language;
  document.documentElement.dir = RIGHT_TO_LEFT.has(language) ? "rtl" : "ltr";
}

export { i18n };
