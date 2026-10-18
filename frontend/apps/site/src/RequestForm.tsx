import type { SiteProduct, SiteRequest, SiteRequestReceived, WebRequestKindEnum } from "@frutti/api";
import { formatMoney, useTranslation } from "@frutti/i18n";
import { cn, Icon } from "@frutti/ui";
import { useMutation } from "@tanstack/react-query";
import { type ReactNode, useId, useMemo, useState } from "react";

import { ApiError, sendSiteRequest } from "./api";
import { type CartLine, estimate, lineTotal, parseKilos, removeFromCart, setQuantity } from "./cart";
import { pictureOf } from "./media";
import { useReveal } from "./motion";
import { normalizePhone } from "./phone";

type Contact = {
  full_name: string;
  phone: string;
  email: string;
  company: string;
  city: string;
  address: string;
  wanted_on: string;
  message: string;
  // Never shown to people: only robots fill it, and the server refuses the request then.
  website: string;
};

const EMPTY: Contact = {
  full_name: "",
  phone: "",
  email: "",
  company: "",
  city: "",
  address: "",
  wanted_on: "",
  message: "",
  website: "",
};

const inputClass =
  "w-full rounded-control border border-line bg-surface px-3.5 py-3 text-ink transition focus:border-sea aria-[invalid=true]:border-bad";

function Labeled({
  id,
  label,
  error,
  hint,
  required = false,
  children,
  className,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const { t } = useTranslation();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[0.85rem] font-semibold">
        {label}
        {required && (
          <span className="text-coral" title={t("site.form.required")}>
            {" "}
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-[0.8rem] font-semibold text-bad">
          {error}
        </p>
      ) : (
        hint && <p className="text-[0.8rem] text-ink-2">{hint}</p>
      )}
    </div>
  );
}

function without<K extends PropertyKey, V>(record: Record<K, V>, key: K): Record<K, V> {
  const copy = { ...record };
  delete copy[key];
  return copy;
}

/** The server's 400 answer as one message per field. */
function serverErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.status !== 400 || typeof error.body !== "object" || !error.body) return {};
  const errors: Record<string, string> = {};
  for (const [field, messages] of Object.entries(error.body)) {
    if (Array.isArray(messages) && typeof messages[0] === "string") errors[field] = messages[0];
    else if (typeof messages === "string") errors[field] = messages;
  }
  return errors;
}

/** The basket and the contact form: an order, or a quote request. The phone number is required (D-184). */
export function RequestForm({
  kind,
  onKind,
  cart,
  onCart,
  products,
}: {
  kind: WebRequestKindEnum;
  onKind: (kind: WebRequestKindEnum) => void;
  cart: CartLine[];
  onCart: (lines: CartLine[]) => void;
  products: SiteProduct[];
}) {
  const { t } = useTranslation();
  const ref = useReveal<HTMLDivElement>();
  const formId = useId();
  const field = (name: keyof Contact) => `${formId}-${name}`;
  const [contact, setContact] = useState<Contact>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [received, setReceived] = useState<(SiteRequestReceived & { phone: string }) | null>(null);
  const byId = useMemo(() => new Map(products.map((product) => [product.id, product])), [products]);
  const prices = useMemo(() => new Map(products.map((product) => [product.id, product.web_price])), [products]);
  const lines = cart.filter((line) => byId.has(line.product));
  const total = estimate(lines, prices);
  const [typed, setTyped] = useState<Record<number, string>>({});

  const update = (name: keyof Contact, value: string) => {
    setContact((current) => ({ ...current, [name]: value }));
    if (errors[name]) setErrors((current) => without(current, name));
  };

  const send = useMutation({
    mutationFn: (body: SiteRequest) => sendSiteRequest(body),
    onSuccess: (answer, body) => {
      setReceived({ ...answer, phone: body.phone });
      onCart([]);
      setContact(EMPTY);
      setTyped({});
    },
    onError: (failure) => {
      if (failure instanceof ApiError && failure.status === 429) setErrors({ form: t("site.form.tooMany") });
      else {
        const fromServer = serverErrors(failure);
        setErrors(Object.keys(fromServer).length > 0 ? fromServer : { form: t("site.form.failed") });
      }
    },
  });

  const submit = () => {
    const found: Record<string, string> = {};
    const phone = normalizePhone(contact.phone);
    if (!contact.full_name.trim()) found.full_name = t("site.form.wrongName");
    if (!phone) found.phone = t("site.form.wrongPhone");
    if (lines.some((line) => !parseKilos(line.quantity))) found.lines = t("site.form.wrongQuantity");
    else if (kind === "order" && lines.length === 0) found.lines = t("site.form.needProduct");
    else if (kind === "quote" && lines.length === 0 && !contact.message.trim())
      found.lines = t("site.form.needSomething");
    setErrors(found);
    if (Object.keys(found).length > 0 || !phone) return;
    send.mutate({
      kind,
      full_name: contact.full_name.trim(),
      phone,
      email: contact.email.trim(),
      company: contact.company.trim(),
      city: contact.city.trim(),
      address: contact.address.trim(),
      wanted_on: contact.wanted_on || null,
      message: contact.message.trim(),
      website: contact.website,
      lines: lines.map((line) => ({ product: line.product, quantity: line.quantity })),
    });
  };

  const input = (name: keyof Contact, props: Record<string, unknown> = {}) => ({
    id: field(name),
    value: contact[name],
    onChange: (event: { target: { value: string } }) => update(name, event.target.value),
    "aria-invalid": errors[name] ? true : undefined,
    "aria-describedby": errors[name] ? `${field(name)}-error` : undefined,
    className: inputClass,
    ...props,
  });

  return (
    <section id="commande" className="relative overflow-hidden py-20 md:py-28">
      <div
        aria-hidden
        className="absolute -top-40 -right-40 -z-10 size-[520px] rounded-full bg-[radial-gradient(circle,var(--sea-soft)_0%,transparent_70%)]"
      />
      <div ref={ref} className="reveal site-container">
        <p className="eyebrow text-coral">{t("site.form.eyebrow")}</p>
        <h2 className="mt-2 font-display text-[clamp(2rem,4.5vw,3.25rem)] leading-[1.05] font-extrabold">
          {t("site.form.title")}
        </h2>
        <p className="mt-3 max-w-2xl text-[1.02rem] text-ink-2">{t("site.form.intro")}</p>

        {received ? (
          <div className="mt-10 max-w-2xl rounded-[24px] border border-line bg-surface p-8 shadow-card">
            <div className="pop grid size-14 place-items-center rounded-full bg-good-soft text-good">
              <Icon name="check" className="size-7" />
            </div>
            <h3 className="mt-5 font-display text-[1.6rem] font-extrabold">{t("site.form.thanksTitle")}</h3>
            <p className="mt-2 text-[1.05rem] text-ink-2">
              {t(received.kind === "order" ? "site.form.thanksOrder" : "site.form.thanksQuote", {
                number: received.number,
                // Kept on one line: a number cut in two is easy to misread.
                phone: received.phone.replaceAll(" ", "\u00a0"),
              })}
            </p>
            <button
              type="button"
              onClick={() => setReceived(null)}
              className="mt-6 rounded-full border border-line px-5 py-2.5 font-semibold hover:border-sea hover:text-sea"
            >
              {t("site.form.again")}
            </button>
          </div>
        ) : (
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
            className="mt-10 grid gap-8 lg:grid-cols-[1fr_1.15fr]"
          >
            <div className="flex flex-col gap-4">
              <div role="radiogroup" className="grid grid-cols-2 rounded-full bg-surface-2 p-1.5">
                {(["order", "quote"] as const).map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    role="radio"
                    aria-checked={kind === choice}
                    onClick={() => onKind(choice)}
                    className={cn(
                      "rounded-full px-4 py-2.5 font-bold text-ink-2 transition",
                      kind === choice && "bg-[#0c2633] text-white shadow-card",
                    )}
                  >
                    {t(`site.form.${choice}`)}
                  </button>
                ))}
              </div>
              <p className="text-[0.92rem] text-ink-2">
                {t(kind === "order" ? "site.form.orderHint" : "site.form.quoteHint")}
              </p>

              <div className="rounded-[22px] border border-line bg-surface p-5 shadow-card">
                <h3 className="flex items-center gap-2">
                  <Icon name="cart" className="text-coral" />
                  {t("site.form.basket")}
                </h3>
                {lines.length === 0 ? (
                  <p className="mt-3 text-[0.92rem] text-ink-2">
                    {t(kind === "order" ? "site.form.basketEmpty" : "site.form.basketEmptyQuote")}
                  </p>
                ) : (
                  <ul className="mt-3 flex flex-col divide-y divide-line">
                    {lines.map((line) => {
                      const product = byId.get(line.product);
                      if (!product) return null;
                      const text = typed[line.product] ?? line.quantity;
                      return (
                        <li key={line.product} className="flex items-center gap-3 py-3">
                          <img src={pictureOf(product)} alt="" className="size-12 rounded-control object-cover" />
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-semibold">{product.name}</div>
                            <div className="text-[0.8rem] text-ink-2">
                              {product.web_price
                                ? `${formatMoney(product.web_price)} ${t("site.products.perKg")} · ${formatMoney(lineTotal(line.quantity, product.web_price))}`
                                : t("site.products.onRequest")}
                            </div>
                          </div>
                          <input
                            inputMode="decimal"
                            aria-label={`${t("site.products.quantity")} · ${product.name}`}
                            value={text}
                            onChange={(event) => {
                              const value = event.target.value;
                              setTyped((current) => ({ ...current, [line.product]: value }));
                              const kilos = parseKilos(value);
                              if (kilos) onCart(setQuantity(cart, line.product, kilos));
                            }}
                            onBlur={() => setTyped((current) => without(current, line.product))}
                            className="num w-20 rounded-control border border-line bg-surface px-2 py-1.5 text-end"
                          />
                          <span className="text-[0.8rem] text-ink-2">kg</span>
                          <button
                            type="button"
                            aria-label={t("site.form.remove", { name: product.name })}
                            onClick={() => onCart(removeFromCart(cart, line.product))}
                            className="grid size-8 place-items-center rounded-full text-ink-2 hover:bg-bad-soft hover:text-bad"
                          >
                            <Icon name="trash" className="size-4" />
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {total && (
                  <div className="mt-3 border-t border-line pt-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="font-semibold">{t("site.form.estimate")}</span>
                      <span className="num text-[1.2rem] font-bold text-sea">{formatMoney(total)}</span>
                    </div>
                    <p className="mt-1 text-[0.78rem] text-ink-2">{t("site.form.estimateNote")}</p>
                  </div>
                )}
                {errors.lines && <p className="mt-3 text-[0.85rem] font-semibold text-bad">{errors.lines}</p>}
              </div>
            </div>

            <div className="grid gap-4 rounded-[22px] border border-line bg-surface p-6 shadow-card sm:grid-cols-2">
              <Labeled id={field("full_name")} label={t("site.form.name")} error={errors.full_name} required>
                <input {...input("full_name", { autoComplete: "name", maxLength: 120 })} />
              </Labeled>
              <Labeled
                id={field("phone")}
                label={t("site.form.phone")}
                error={errors.phone}
                hint={t("site.form.phoneHint")}
                required
              >
                <input {...input("phone", { type: "tel", autoComplete: "tel", inputMode: "tel", maxLength: 30 })} />
              </Labeled>
              <Labeled id={field("company")} label={t("site.form.company")} error={errors.company}>
                <input {...input("company", { autoComplete: "organization", maxLength: 150 })} />
              </Labeled>
              <Labeled id={field("email")} label={t("site.form.email")} error={errors.email}>
                <input {...input("email", { type: "email", autoComplete: "email" })} />
              </Labeled>
              <Labeled id={field("city")} label={t("site.form.city")} error={errors.city}>
                <input {...input("city", { autoComplete: "address-level2", maxLength: 100 })} />
              </Labeled>
              <Labeled id={field("wanted_on")} label={t("site.form.wantedOn")} error={errors.wanted_on}>
                <input {...input("wanted_on", { type: "date" })} />
              </Labeled>
              <Labeled
                id={field("address")}
                label={t("site.form.address")}
                error={errors.address}
                className="sm:col-span-2"
              >
                <input {...input("address", { autoComplete: "street-address", maxLength: 250 })} />
              </Labeled>
              <Labeled
                id={field("message")}
                label={t("site.form.message")}
                error={errors.message}
                className="sm:col-span-2"
              >
                <textarea
                  {...input("message", { rows: 4, maxLength: 2000, placeholder: t("site.form.messagePlaceholder") })}
                />
              </Labeled>
              <div aria-hidden className="absolute -left-[9999px]" tabIndex={-1}>
                <label htmlFor={field("website")}>Website</label>
                <input {...input("website", { tabIndex: -1, autoComplete: "off" })} />
              </div>

              <div className="flex flex-col gap-3 sm:col-span-2">
                {errors.form && (
                  <p role="alert" className="rounded-control bg-bad-soft p-3 text-[0.9rem] font-semibold text-bad">
                    {errors.form}
                  </p>
                )}
                {(errors.detail ?? errors.kind) && (
                  <p role="alert" className="rounded-control bg-bad-soft p-3 text-[0.9rem] font-semibold text-bad">
                    {errors.detail ?? errors.kind}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={send.isPending}
                  className="group flex items-center justify-center gap-2 rounded-full bg-coral px-6 py-4 text-[1.05rem] font-bold text-white shadow-[0_12px_32px_-12px_rgba(232,96,76,0.9)] transition hover:-translate-y-0.5 hover:brightness-105 disabled:opacity-60"
                >
                  {send.isPending
                    ? t("site.form.sending")
                    : t(kind === "order" ? "site.form.send" : "site.form.sendQuote")}
                  <span aria-hidden className="transition group-hover:translate-x-1">
                    →
                  </span>
                </button>
                <p className="text-center text-[0.78rem] text-ink-2">{t("site.form.privacy")}</p>
              </div>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
