import type { LocationTotal, Product, ProductStock } from "@frutti/api";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { cn, Pill } from "@frutti/ui";
import { Link } from "react-router";

import { ProductPicture } from "../products/ProductCard";

// One colour per place in the distribution bar, in the order of the location cards.
const BAR_COLORS = ["bg-sea", "bg-coral", "bg-warn", "bg-good", "bg-ink-2"];

/** What a product costs to buy: the weighted average over the stock on hand, and the last batch's price. */
export function PurchasePrices({ stock, className }: { stock: ProductStock; className?: string }) {
  const { t } = useTranslation();
  const price = (value: string | null) =>
    value === null ? (
      t("admin.stock.none")
    ) : (
      <>
        <span className="num font-semibold">{formatMoney(value)}</span>
        <span className="text-[0.75rem] text-ink-2"> {t("admin.stock.perKg")}</span>
      </>
    );
  return (
    <dl className={cn("grid grid-cols-2 gap-2", className)}>
      <div>
        <dt className="text-[0.72rem] font-semibold text-ink-2">{t("admin.stock.averageCost")}</dt>
        <dd data-testid="average-cost">{price(stock.average_cost)}</dd>
      </div>
      <div>
        <dt className="text-[0.72rem] font-semibold text-ink-2">{t("admin.stock.lastCost")}</dt>
        <dd data-testid="last-cost">{price(stock.last_cost)}</dd>
      </div>
    </dl>
  );
}

/** A product of the stock page like the prototype's: picture, kg per place, low-stock badge. */
export function StockProductCard({ stock, places }: { stock: ProductStock; places: readonly LocationTotal[] }) {
  const { t } = useTranslation();
  const total = Number(stock.quantity);
  const kg = (placeId: number) => stock.locations.find((row) => row.location_id === placeId)?.quantity ?? "0.000";
  const held = places.filter((place) => Number(kg(place.id)) > 0);
  return (
    <article
      aria-label={stock.name}
      className={cn(
        "relative flex min-w-0 flex-col overflow-hidden rounded-card border border-line bg-surface shadow-card transition-[border-color] hover:border-sea",
        !stock.is_active && "opacity-70",
      )}
    >
      <div className="relative">
        <ProductPicture photoUrl={stock.photo_url} illustration={stock.illustration as Product["illustration"]} />
        <span className="num absolute start-2.5 top-2.5 rounded-[6px] bg-surface px-[7px] py-0.5 text-[0.7rem] font-medium text-ink-2">
          {stock.reference}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2.5 px-4 pt-3.5 pb-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="min-w-0 [overflow-wrap:anywhere]">
            {/* The link covers the whole card (after:inset-0): a click anywhere opens the product. */}
            <Link
              to={`/stock/produits/${stock.id}`}
              className="after:absolute after:inset-0 after:rounded-card focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-sea"
            >
              {stock.name}
            </Link>
          </h3>
          <span className="flex-none text-end">
            <span className="num font-semibold">{formatQuantity(stock.quantity)}</span>
          </span>
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
          {places.map((place, index) => {
            const share = total > 0 ? (Number(kg(place.id)) / total) * 100 : 0;
            return share > 0 ? (
              <i key={place.id} className={BAR_COLORS[index % BAR_COLORS.length]} style={{ width: `${share}%` }} />
            ) : null;
          })}
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(5.5rem,1fr))] gap-2">
          {held.map((place) => (
            <div key={place.id} className="min-w-0">
              <span className="block truncate text-[0.72rem] font-semibold text-ink-2" title={place.name}>
                {place.name}
              </span>
              <b className="num">{formatQuantity(kg(place.id))}</b>
            </div>
          ))}
        </div>
        <PurchasePrices stock={stock} />
        <div className="mt-auto flex items-center justify-between gap-2">
          <span className="text-[0.8rem] text-ink-2">
            {stock.min_stock !== "0.000" && t("admin.stock.minimum", { quantity: formatQuantity(stock.min_stock) })}
          </span>
          {stock.is_low ? (
            <Pill tone="bad">{t("admin.stock.low")}</Pill>
          ) : (
            <Pill tone="good">{t("admin.stock.enough")}</Pill>
          )}
        </div>
      </div>
    </article>
  );
}
