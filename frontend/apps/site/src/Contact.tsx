import type { SiteContact } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { BRAND, BrandMark, cn } from "@frutti/ui";
import type { SVGProps } from "react";

import { shownPhone, telHref } from "./phone";

/** The company logo uploaded in the office app (on a white tile, so a dark logo stays readable on the dark header),
 * else the brand mark; then the company name. */
export function Logo({ logoUrl, name }: { logoUrl: string | null | undefined; name: string | undefined }) {
  return (
    <span className="flex items-center gap-2.5 font-display text-[1.15rem] font-extrabold">
      {logoUrl ? (
        <span className="grid h-10 min-w-10 place-items-center rounded-[10px] bg-white px-1.5 shadow-sm">
          <img src={logoUrl} alt="" className="h-8 w-auto max-w-[120px] object-contain" />
        </span>
      ) : (
        <BrandMark className="bg-coral" />
      )}
      {name ?? BRAND.name}
    </span>
  );
}

// The two drawings the shared sprite does not have.
export function PhoneIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className={cn("size-5 flex-none fill-none stroke-current", className)}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
    </svg>
  );
}

export function WhatsAppIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className={cn("size-5 flex-none fill-none stroke-current", className)}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M3 21l1.65-3.8a9 9 0 1 1 3.4 2.9L3 21" />
      <path d="M9.5 9c0 3 2.5 5.5 5.5 5.5l1-1.5-2-1-1 .8a4 4 0 0 1-1.8-1.8l.8-1-1-2z" />
    </svg>
  );
}

/** A round "call" button at the bottom of a phone's screen, when the office has set a number (D-186). */
export function CallButton({ contact }: { contact: SiteContact | undefined }) {
  const { t } = useTranslation();
  if (!contact?.phone) return null;
  return (
    <a
      href={telHref(contact.phone)}
      aria-label={t("site.contact.call", { phone: shownPhone(contact.phone) })}
      className="pop fixed end-4 bottom-4 z-40 grid size-14 place-items-center rounded-full bg-good text-white shadow-[0_12px_32px_-10px_rgba(31,138,91,0.9)] md:hidden"
    >
      <PhoneIcon className="size-6" />
    </a>
  );
}
