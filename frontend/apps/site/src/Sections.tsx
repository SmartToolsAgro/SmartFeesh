import type { SiteContact } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Icon, type IconName } from "@frutti/ui";
import type { CSSProperties } from "react";

import { Logo, PhoneIcon, WhatsAppIcon } from "./Contact";
import { CATCH } from "./media";
import { useParallax, useReveal } from "./motion";
import { shownPhone, telHref, whatsappHref } from "./phone";

/** The names of the catch, running across the page. */
export function Marquee() {
  const { t } = useTranslation();
  const names = t("site.marquee", { returnObjects: true });
  const row = [...names, ...names];
  return (
    <div aria-hidden className="marquee overflow-hidden border-y border-line bg-surface py-5">
      <div className="marquee-track">
        {row.map((name, index) => (
          <span
            key={index}
            className="flex items-center gap-6 px-6 font-display text-[clamp(1.4rem,3vw,2.2rem)] font-extrabold whitespace-nowrap text-ink/80"
          >
            {name}
            <Icon name="snow" className="size-5 text-coral" />
          </span>
        ))}
      </div>
    </div>
  );
}

const VALUE_ICONS: IconName[] = ["anchor", "truck"];

function ValueCard({ figure, label, body, index }: { figure: string; label: string; body: string; index: number }) {
  const ref = useReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className="reveal card-lift rounded-[20px] border border-line bg-surface p-6 shadow-card"
      style={{ "--delay": `${index * 110}ms` } as CSSProperties}
    >
      <div className="grid size-11 place-items-center rounded-full bg-sea-soft text-sea">
        <Icon name={VALUE_ICONS[index] ?? "check"} />
      </div>
      <div className="mt-5 font-display text-[2rem] leading-none font-extrabold text-sea">{figure}</div>
      <h3 className="mt-2 text-[1.05rem]">{label}</h3>
      <p className="mt-2 text-[0.95rem] text-ink-2">{body}</p>
    </div>
  );
}

export function Values() {
  const { t } = useTranslation();
  const title = useReveal<HTMLHeadingElement>();
  const items = t("site.values.items", { returnObjects: true });
  return (
    <section id="valeurs" className="site-container py-20 md:py-28">
      <h2
        ref={title}
        className="reveal max-w-2xl font-display text-[clamp(2rem,4.5vw,3.25rem)] leading-[1.05] font-extrabold"
      >
        {t("site.values.title")}
      </h2>
      <div className="mt-10 grid max-w-4xl gap-5 sm:grid-cols-2">
        {items.map((item, index) => (
          <ValueCard key={item.label} {...item} index={index} />
        ))}
      </div>
    </section>
  );
}

function Step({ title, body, index }: { title: string; body: string; index: number }) {
  const ref = useReveal<HTMLLIElement>();
  return (
    <li ref={ref} className="reveal relative ps-16" style={{ "--delay": `${index * 140}ms` } as CSSProperties}>
      <span className="absolute start-0 top-0 grid size-11 place-items-center rounded-full bg-coral font-display text-[1.1rem] font-extrabold text-white shadow-[0_10px_24px_-10px_rgba(232,96,76,0.9)]">
        {index + 1}
      </span>
      <h3 className="text-[1.2rem] text-white">{title}</h3>
      <p className="mt-1.5 text-white/75">{body}</p>
    </li>
  );
}

/** From the quay to the customer, over the catch photo that slides slower than the page. */
export function Story() {
  const { t } = useTranslation();
  const section = useReveal<HTMLDivElement>();
  const picture = useParallax<HTMLImageElement>(0.12);
  const steps = t("site.story.steps", { returnObjects: true });
  return (
    <section id="metier" className="relative isolate overflow-hidden bg-[#0c2633] py-24 text-white md:py-32">
      <img
        ref={picture}
        src={CATCH}
        alt=""
        loading="lazy"
        className="absolute inset-x-0 -top-[15%] -z-20 h-[130%] w-full object-cover opacity-45"
      />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(7,26,35,0.95)_0%,rgba(7,26,35,0.75)_55%,rgba(7,26,35,0.35)_100%)]" />
      <div ref={section} className="reveal site-container grid gap-12 md:grid-cols-[1fr_1.1fr]">
        <div>
          <p className="eyebrow text-white/70">{t("site.story.eyebrow")}</p>
          <h2 className="mt-3 font-display text-[clamp(2rem,4.5vw,3.25rem)] leading-[1.05] font-extrabold">
            {t("site.story.title")}
          </h2>
        </div>
        <ol className="flex flex-col gap-9">
          {steps.map((step, index) => (
            <Step key={step.title} {...step} index={index} />
          ))}
        </ol>
      </div>
    </section>
  );
}

const YEAR = new Date().getFullYear();

export function Footer({
  company,
  logoUrl,
  contact,
}: {
  company?: string;
  logoUrl?: string | null;
  contact?: SiteContact;
}) {
  const { t } = useTranslation();
  return (
    <footer id="contact" className="bg-[#071a23] py-14 text-white/80">
      <div className="site-container grid gap-10 md:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5 font-display text-[1.2rem] font-extrabold text-white">
            <Logo logoUrl={logoUrl} name={company} />
          </div>
          <p className="mt-3 max-w-sm">{t("site.footer.tagline")}</p>
        </div>
        <div className="flex flex-col gap-2">
          <span className="eyebrow text-white/50">{t("site.nav.contact")}</span>
          {contact?.phone && (
            <a
              href={telHref(contact.phone)}
              className="flex items-center gap-2 font-semibold text-white hover:underline"
            >
              <PhoneIcon className="size-4" />
              <span className="num">{shownPhone(contact.phone)}</span>
            </a>
          )}
          {contact?.whatsapp && (
            <a
              href={whatsappHref(contact.whatsapp)}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 hover:text-white"
            >
              <WhatsAppIcon className="size-4" />
              {t("site.contact.whatsapp")}
            </a>
          )}
          {contact?.email && (
            <a href={`mailto:${contact.email}`} className="flex items-center gap-2 hover:text-white">
              <Icon name="receipt" className="size-4" />
              {contact.email}
            </a>
          )}
          <span className="flex items-center gap-2">
            <Icon name="pin" className="size-4" />
            {contact?.address || t("site.footer.address")}
          </span>
          {contact?.opening_hours && (
            <span className="flex items-center gap-2">
              <Icon name="calcheck" className="size-4" />
              {contact.opening_hours}
            </span>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <a href="#produits" className="hover:text-white">
            {t("site.nav.products")}
          </a>
          <a href="#commande" className="hover:text-white">
            {t("site.nav.order")}
          </a>
        </div>
      </div>
      <div className="site-container mt-10 border-t border-white/10 pt-6 text-[0.85rem] text-white/50">
        {t("site.footer.rights", { year: YEAR })}
      </div>
    </footer>
  );
}
