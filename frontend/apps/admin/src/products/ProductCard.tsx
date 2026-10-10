import type { Product } from "@frutti/api";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { cn, Icon, Illustration, Pill } from "@frutti/ui";

import { storageRange } from "./shared";

/** The photo, or the product's drawing on the prototype's ice-blue tile. */
export function ProductPicture({
  photoUrl,
  illustration,
  className,
}: {
  photoUrl: string | null;
  illustration: Product["illustration"];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative grid aspect-[16/10] place-items-center overflow-hidden bg-radial-[120%_90%_at_30%_20%] from-tile-a to-tile-b",
        className,
      )}
    >
      {photoUrl ? (
        <img src={photoUrl} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />
      ) : (
        <Illustration name={illustration} className="h-[80%] w-[72%]" />
      )}
    </div>
  );
}

/** One product of the catalogue, laid out like the prototype's stock cards. */
export function ProductCard({ product, onOpen }: { product: Product; onOpen?: () => void }) {
  const { t } = useTranslation();
  const range = storageRange(product);
  const body = (
    <>
      <div className="relative">
        <ProductPicture photoUrl={product.photo_url} illustration={product.illustration} />
        <span className="num absolute start-2.5 top-2.5 rounded-[6px] bg-surface px-[7px] py-0.5 text-[0.7rem] font-medium text-ink-2">
          {product.reference}
        </span>
        {range && (
          <span className="num absolute end-2.5 top-2.5 flex items-center gap-[3px] rounded-[6px] bg-surface px-[7px] py-0.5 text-[0.72rem] font-semibold text-sea">
            <Icon name="snow" className="size-[13px]" />
            {range}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2.5 px-4 pt-3.5 pb-4">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="min-w-0 [overflow-wrap:anywhere]">
            {onOpen ? (
              // The button covers the whole card (after:inset-0), so a click anywhere opens the product.
              <button
                type="button"
                onClick={onOpen}
                className="text-start after:absolute after:inset-0 after:rounded-card focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-sea"
              >
                {product.name}
              </button>
            ) : (
              product.name
            )}
          </h3>
          <span className="flex-none text-end">
            {product.current_price ? (
              <>
                <span className="num font-semibold">{formatMoney(product.current_price)}</span>
                <span className="text-[0.75rem] text-ink-2"> {t("admin.products.perKg")}</span>
              </>
            ) : (
              <span className="text-ink-2">{t("admin.products.noPrice")}</span>
            )}
          </span>
        </div>
        {product.name_ar && (
          <p lang="ar" dir="rtl" className="-mt-1.5 text-start text-[0.85rem] text-ink-2">
            {product.name_ar}
          </p>
        )}
        <div className="mt-auto flex items-center justify-between gap-2">
          <span className="text-[0.8rem] text-ink-2">{product.category.name}</span>
          {product.is_active ? (
            <Pill tone="sea">{t("admin.products.minStock", { quantity: formatQuantity(product.min_stock) })}</Pill>
          ) : (
            <Pill tone="neutral">{t("admin.products.archived")}</Pill>
          )}
        </div>
      </div>
    </>
  );
  return (
    <article
      className={cn(
        "relative flex min-w-0 flex-col overflow-hidden rounded-card border border-line bg-surface shadow-card",
        onOpen && "transition-[border-color] hover:border-sea",
        !product.is_active && "opacity-70",
      )}
    >
      {body}
    </article>
  );
}
