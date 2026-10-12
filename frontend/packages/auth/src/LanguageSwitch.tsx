import { applyLanguage, currentLanguage, type Language, LANGUAGES, useTranslation } from "@frutti/i18n";
import { cn } from "@frutti/ui";

import { chooseLanguageBeforeLogin, useSession, useSetLanguage } from "./session";

// Each language is always written in itself, so a driver finds theirs whatever the screen says now.
const NAMES: Record<Language, string> = { fr: "Français", ar: "العربية" };

/**
 * French or Arabic. Logged out (login screen) it only changes this page, and the choice is saved on the
 * account at login; logged in it is saved on the account at once (P3-T09, D-103).
 */
export function LanguageSwitch({ className }: { className?: string }) {
  const { t } = useTranslation();
  const session = useSession();
  const save = useSetLanguage();
  const active = session.data?.user.language ?? currentLanguage();

  function choose(language: Language) {
    if (language === active) return;
    if (session.data) {
      save.mutate(language);
    } else {
      chooseLanguageBeforeLogin(language);
      applyLanguage(language);
    }
  }

  return (
    <div
      role="group"
      aria-label={t("language.label")}
      className={cn("flex rounded-full border border-line bg-surface-2 p-[3px]", className)}
    >
      {LANGUAGES.map((language) => (
        <button
          key={language}
          type="button"
          lang={language}
          aria-pressed={active === language}
          onClick={() => choose(language)}
          className="rounded-full px-3 py-1 text-[0.82rem] font-semibold text-ink-2 aria-pressed:bg-ink aria-pressed:text-surface"
        >
          {NAMES[language]}
        </button>
      ))}
    </div>
  );
}
