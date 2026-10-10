import type { PartialTranslation } from "./fr";

/**
 * Arabic is not translated yet (the driver app is translated in P3-T09). These few texts only prove
 * that switching language and reading direction works; every other key falls back to French.
 */
export const ar: PartialTranslation = {
  common: {
    currency: "د.ت",
    logout: "تسجيل الخروج",
  },
  auth: {
    title: "تسجيل الدخول",
  },
};
