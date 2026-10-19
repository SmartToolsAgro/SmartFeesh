import type { SiteCatalog, SiteProduct } from "@frutti/api";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { cn, Icon, toast } from "@frutti/ui";
import type { UseQueryResult } from "@tanstack/react-query";
import { type CSSProperties, useId, useState } from "react";

import { type CartLine, parseKilos } from "./cart";
import { pictureOf } from "./media";
import { useReveal } from "./motion";

const STEPS = ["1", "2", "5", "10"] as const;

function ProductCard({
  product,
  inCart,
  index,
  onAdd,
}: {
  product: SiteProduct;
  inCart: CartLine | undefined;
  index: number;
  onAdd: (product: number, quantity: string) => void;
}) {
  const { t } = useTranslation();
  const ref = useReveal<HTMLElement>();
  const quantityId = useId();
  const [quantity, setQuantity] = useState("1");
  const kilos = parseKilos(quantity);

  return (
    <article
      ref={ref}
      className="reveal card-lift flex flex-col overflow-hidden rounded-[22px] border border-line bg-surface shadow-card"
      style={{ "--delay": `${(index % 3) * 90}ms` } as CSSProperties}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-[#0c2633]">
        <img src={pictureOf(product)} alt={product.name} loading="lazy" className="zoom size-full object-cover" />
        <span className="absolute start-3 top-3 rounded-full bg-[#0c2633]/70 px-3 py-1 text-[0.75rem] font-semibold text-white backdrop-blur">
          {product.category_name}
        </span>
        {inCart && (
          <span className="absolute end-3 top-3 flex items-center gap-1 rounded-full bg-coral px-3 py-1 text-[0.75rem] font-bold text-white">
            <Icon name="check" className="size-3.5" />
            {t("site.products.inBasket", { quantity: formatQuantity(inCart.quantity) })}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-[1.2rem] leading-tight">{product.name}</h3>
            {product.name_ar && (
              <p lang="ar" dir="rtl" className="mt-0.5 text-[0.9rem] text-ink-2">
                {product.name_ar}
              </p>
            )}
          </div>
          <div className="text-end">
            {product.web_price ? (
              <>
                <div className="num text-[1.1rem] font-bold whitespace-nowrap text-sea">
                  {formatMoney(product.web_price)}
                </div>
                <div className="text-[0.75rem] text-ink-2">{t("site.products.perKg")}</div>
              </>
            ) : (
              <div className="rounded-full bg-sea-soft px-2.5 py-1 text-[0.75rem] font-semibold whitespace-nowrap text-sea">
                {t("site.products.onRequest")}
              </div>
            )}
          </div>
        </div>
        {product.description && <p className="text-[0.92rem] text-ink-2">{product.description}</p>}

        <form
          className="mt-auto flex flex-col gap-2 pt-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!kilos) return;
            onAdd(product.id, kilos);
            toast.success(t("site.products.added", { name: product.name }));
          }}
        >
          <label htmlFor={quantityId} className="text-[0.78rem] font-semibold text-ink-2">
            {t("site.products.quantity")}
          </label>
          <div className="flex gap-2">
            <input
              id={quantityId}
              inputMode="decimal"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              aria-invalid={kilos ? undefined : true}
              className={cn(
                "num w-20 rounded-control border bg-surface px-3 py-2 text-ink",
                kilos ? "border-line" : "border-bad",
              )}
            />
            <div className="flex flex-1 gap-1">
              {STEPS.map((step) => (
                <button
                  key={step}
                  type="button"
                  onClick={() => setQuantity(step)}
                  aria-pressed={quantity === step}
                  className={cn(
                    "flex-1 rounded-control border border-line text-[0.85rem] font-semibold text-ink-2 transition hover:border-sea hover:text-sea",
                    quantity === step && "border-sea bg-sea-soft text-sea",
                  )}
                >
                  {step}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={!kilos}
            className="flex items-center justify-center gap-2 rounded-control bg-[#0c2633] px-4 py-2.5 font-bold text-white transition hover:bg-sea disabled:opacity-50"
          >
            <Icon name="plus" />
            {t("site.products.add")}
          </button>
        </form>
      </div>
    </article>
  );
}

/** The products the office put on the site, filtered by category. */
export function Products({
  catalog,
  cart,
  onAdd,
}: {
  catalog: UseQueryResult<SiteCatalog, unknown>;
  cart: readonly CartLine[];
  onAdd: (product: number, quantity: string) => void;
}) {
  const { t } = useTranslation();
  const heading = useReveal<HTMLDivElement>();
  const [category, setCategory] = useState<number | null>(null);
  const products = catalog.data?.products ?? [];
  const shown = category === null ? products : products.filter((product) => product.category === category);
  const categories = catalog.data?.categories ?? [];

  return (
    <section id="produits" className="bg-[linear-gradient(180deg,var(--bg)_0%,var(--surface-2)_100%)] py-20 md:py-28">
      <div className="site-container">
        <div ref={heading} className="reveal flex flex-wrap items-end gap-6">
          <div className="max-w-2xl">
            <p className="eyebrow text-coral">{t("site.products.eyebrow")}</p>
            <h2 className="mt-2 font-display text-[clamp(2rem,4.5vw,3.25rem)] leading-[1.05] font-extrabold">
              {t("site.products.title")}
            </h2>
            <p className="mt-3 text-[1.02rem] text-ink-2">{t("site.products.intro")}</p>
          </div>
        </div>

        {categories.length > 1 && (
          <div role="group" className="mt-8 flex flex-wrap gap-2">
            {[{ id: null, name: t("site.products.all") }, ...categories].map((choice) => (
              <button
                key={choice.id ?? "all"}
                type="button"
                aria-pressed={category === choice.id}
                onClick={() => setCategory(choice.id)}
                className={cn(
                  "rounded-full border px-4 py-2 text-[0.9rem] font-semibold transition",
                  category === choice.id
                    ? "border-[#0c2633] bg-[#0c2633] text-white"
                    : "border-line bg-surface text-ink-2 hover:border-sea hover:text-sea",
                )}
              >
                {choice.name}
              </button>
            ))}
          </div>
        )}

        {catalog.isPending ? (
          <p className="mt-10 text-ink-2">{t("site.products.loading")}</p>
        ) : catalog.isError ? (
          <p role="alert" className="mt-10 rounded-card border border-line bg-surface p-5 text-ink-2">
            {t("site.products.error")}
          </p>
        ) : products.length === 0 ? (
          <p className="mt-10 rounded-card border border-line bg-surface p-5 text-ink-2">{t("site.products.empty")}</p>
        ) : (
          <>
            <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((product, index) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  index={index}
                  inCart={cart.find((line) => line.product === product.id)}
                  onAdd={onAdd}
                />
              ))}
            </div>
            <p className="mt-6 text-[0.85rem] text-ink-2">{t("site.products.priceNote")}</p>
          </>
        )}
      </div>
    </section>
  );
}
