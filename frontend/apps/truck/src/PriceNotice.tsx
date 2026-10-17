import { formatDateTime, formatMoney, useTranslation } from "@frutti/i18n";
import { Button, Card } from "@frutti/ui";

import { useOnline } from "./offline";
import { dismissPriceNotice, type PriceChange, usePriceNotices } from "./priceWatch";

/** The price changes the driver has not read yet, on every screen, until each one is acknowledged (P3-T02). */
export function PriceNotice() {
  const { t } = useTranslation();
  const notices = usePriceNotices();
  if (notices.length === 0) return null;
  const describe = (change: PriceChange) => {
    if (change.from !== null && change.to !== null) {
      return t("truck.prices.changed", {
        product: change.productName,
        from: formatMoney(change.from),
        to: formatMoney(change.to),
      });
    }
    if (change.to !== null) return t("truck.prices.set", { product: change.productName, to: formatMoney(change.to) });
    return t("truck.prices.removed", { product: change.productName });
  };
  return (
    <Card role="alert" className="space-y-3 border-warn">
      <p className="font-semibold">{t("truck.prices.title")}</p>
      <ul className="space-y-2">
        {notices.map((change) => (
          <li key={change.productId} className="flex items-center justify-between gap-3">
            <span>{describe(change)}</span>
            <Button onClick={() => dismissPriceNotice(change.productId)}>{t("truck.prices.ok")}</Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Under a price list, when the phone is offline: the date and time the prices were last received. */
export function PricesAsOf({ updatedAt }: { updatedAt: number }) {
  const { t } = useTranslation();
  const online = useOnline();
  if (online || updatedAt === 0) return null;
  return (
    <p className="text-sm text-ink-2">
      {t("truck.prices.asOf", { time: formatDateTime(new Date(updatedAt).toISOString()) })}
    </p>
  );
}
