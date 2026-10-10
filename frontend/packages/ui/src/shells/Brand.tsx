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

/** The mark with the company name and tagline, as in the top bar of the prototype. */
export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5 font-display text-[1.15rem] font-extrabold whitespace-nowrap">
      <BrandMark />
      <div>
        {BRAND.name}
        {!compact && (
          <small className="mt-[3px] block font-sans text-[0.7rem] leading-none font-medium tracking-[0.06em] text-ink-2 uppercase">
            {BRAND.tagline}
          </small>
        )}
      </div>
    </div>
  );
}
