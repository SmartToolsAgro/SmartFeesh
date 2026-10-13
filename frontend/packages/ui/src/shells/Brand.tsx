import { useTranslation } from "@frutti/i18n";

import { BRAND } from "../brand";
import { Icon } from "../icons";
import { cn } from "../lib/cn";

export function BrandMark({ className }: { className?: string }) {
  return (
    <div className={cn("grid size-9 flex-none place-items-center rounded-[10px] bg-sea", className)}>
      <Icon name="snow" className="text-white" />
    </div>
  );
}

/**
 * The mark with the company name and tagline, as in the top bar of the prototype. With the logo uploaded in
 * Paramètres (`logoUrl`), the logo takes the place of the mark (D-125).
 */
export function Brand({ compact = false, logoUrl }: { compact?: boolean; logoUrl?: string | null }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2.5 font-display text-[1.15rem] font-extrabold whitespace-nowrap">
      {logoUrl ? (
        <img src={logoUrl} alt="" className="h-9 w-auto max-w-[120px] flex-none object-contain" />
      ) : (
        <BrandMark />
      )}
      <div>
        {BRAND.name}
        {!compact && (
          <small className="mt-[3px] block font-sans text-[0.7rem] leading-none font-medium tracking-[0.06em] text-ink-2 uppercase">
            {t("brand.tagline")}
          </small>
        )}
      </div>
    </div>
  );
}
