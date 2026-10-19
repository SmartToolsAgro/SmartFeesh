import { useTranslation } from "@frutti/i18n";
import { cn, Icon } from "@frutti/ui";
import { useState } from "react";

import { Logo, PhoneIcon } from "./Contact";
import { useScrolledPast } from "./motion";
import { shownPhone, telHref } from "./phone";

const LINKS = [
  ["#produits", "products"],
  ["#metier", "story"],
  ["#commande", "order"],
  ["#contact", "contact"],
] as const;

/** Clear over the video, frosted once the page scrolls. The basket count pops when something is added. */
export function Header({
  basketCount,
  bump,
  phone,
  logoUrl,
  company,
  onBasket,
}: {
  basketCount: number;
  bump: number;
  phone: string;
  logoUrl: string | null | undefined;
  company: string | undefined;
  onBasket: () => void;
}) {
  const { t } = useTranslation();
  const scrolled = useScrolledPast(40);
  const [open, setOpen] = useState(false);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-40 transition-[background-color,box-shadow,backdrop-filter] duration-500",
        scrolled || open ? "bg-[#0c2633]/85 shadow-lg backdrop-blur-md" : "bg-transparent",
      )}
    >
      <div className="site-container flex h-[68px] items-center gap-4 text-white">
        <a href="#top" className="flex items-center gap-2.5 font-display text-[1.15rem] font-extrabold">
          <Logo logoUrl={logoUrl} name={company} />
        </a>
        <nav aria-label={t("site.nav.menu")} className="ms-auto hidden items-center gap-1 md:flex">
          {LINKS.map(([href, key]) => (
            <a
              key={href}
              href={href}
              className="rounded-full px-3.5 py-2 text-[0.92rem] font-semibold text-white/85 transition hover:bg-white/10 hover:text-white"
            >
              {t(`site.nav.${key}`)}
            </a>
          ))}
        </nav>
        {phone && (
          <a
            href={telHref(phone)}
            className="ms-2 hidden items-center gap-2 rounded-full border border-white/30 px-3.5 py-2 text-[0.92rem] font-bold text-white transition hover:bg-white/10 lg:flex"
          >
            <PhoneIcon className="size-4" />
            <span className="num">{shownPhone(phone)}</span>
          </a>
        )}
        <button
          type="button"
          onClick={onBasket}
          className="relative ms-auto flex items-center gap-2 rounded-full bg-coral px-4 py-2 text-[0.92rem] font-bold text-white shadow-md transition hover:brightness-105 md:ms-2"
        >
          <Icon name="cart" />
          <span className="max-sm:sr-only">{t("site.nav.basket")}</span>
          {basketCount > 0 && (
            <span
              key={bump}
              className="pop grid min-w-6 place-items-center rounded-full bg-white px-1.5 text-[0.78rem] text-coral"
            >
              {basketCount}
            </span>
          )}
        </button>
        <button
          type="button"
          aria-expanded={open}
          aria-label={t("site.nav.menu")}
          onClick={() => setOpen((value) => !value)}
          className="grid size-10 place-items-center rounded-full text-white hover:bg-white/10 md:hidden"
        >
          <span aria-hidden className="flex w-5 flex-col gap-1.5">
            <span className={cn("h-0.5 bg-current transition", open && "translate-y-2 rotate-45")} />
            <span className={cn("h-0.5 bg-current transition", open && "opacity-0")} />
            <span className={cn("h-0.5 bg-current transition", open && "-translate-y-2 -rotate-45")} />
          </span>
        </button>
      </div>
      {open && (
        <nav aria-label={t("site.nav.menu")} className="site-container flex flex-col pb-4 md:hidden">
          {LINKS.map(([href, key]) => (
            <a
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className="rounded-control px-3 py-3 font-semibold text-white/90 hover:bg-white/10"
            >
              {t(`site.nav.${key}`)}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}
