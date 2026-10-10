import { useTranslation } from "@frutti/i18n";

import { cn } from "../lib/cn";
import { type Theme, useTheme } from "../theme";

const OPTIONS: { value: Theme; path: string }[] = [
  // Sun
  {
    value: "light",
    path: "M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  },
  // Half circle: follow the device
  { value: "system", path: "M12 3a9 9 0 1 0 0 18zM12 3a9 9 0 0 1 0 18" },
  // Moon
  { value: "dark", path: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" },
];

/** Light, device or dark. The choice is kept on this device only. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t("theme.label")}
      className={cn("flex rounded-full border border-line bg-surface-2 p-[3px]", className)}
    >
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-label={t(`theme.${option.value}`)}
          aria-pressed={theme === option.value}
          onClick={() => setTheme(option.value)}
          className="grid size-8 place-items-center rounded-full text-ink-2 aria-pressed:bg-ink aria-pressed:text-surface"
        >
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            className="size-[17px] fill-none stroke-current"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d={option.path} />
          </svg>
        </button>
      ))}
    </div>
  );
}
