import { useGetMyDaySummary } from "@frutti/api";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Card } from "@frutti/ui";

import { useTruckStock } from "./myStock";
import { pendingKilos, type QueuedItem, useQueue } from "./queue";

const millimes = (value: string | number) => Math.round(Number(value) * 1000);

/**
 * "Aujourd'hui" at the top of the day: sales, cash to hold, expenses and kilos left on the truck, in one glance (P3-T02
 * follow-up). Kilos and sales still waiting on the phone are counted apart, since the office does not have them yet.
 */
export function TodayAtAGlance({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation();
  const summary = useGetMyDaySummary({ query: { enabled, retry: false } });
  const stock = useTruckStock(enabled);
  const queue = useQueue();
  if (!enabled || summary.data === undefined) return null;

  const { summary: day } = summary.data;
  const promised = pendingKilos(queue);
  const leftMillimes = (stock.data ?? []).reduce(
    (sum, line) => sum + Math.max(millimes(line.quantity) - millimes(promised[line.product_id] ?? 0), 0),
    0,
  );
  const waitingSales = queue.filter((item: QueuedItem) => item.kind === "sale").length;

  return (
    <Card className="space-y-2 p-4">
      <h2>{t("truck.glance.title")}</h2>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
        <div>
          <dt className="text-sm text-ink-2">{t("truck.glance.sales")}</dt>
          <dd className="text-lg font-bold">
            {t("truck.glance.salesCount", { count: day.sales_count })}
            <span className="block text-base font-normal text-ink-2">{formatMoney(day.sales_total)}</span>
          </dd>
        </div>
        <div>
          <dt className="text-sm text-ink-2">{t("truck.glance.cash")}</dt>
          <dd className="text-lg font-bold">{formatMoney(day.expected_cash)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-2">{t("truck.glance.expenses")}</dt>
          <dd className="text-lg font-bold">{formatMoney(day.expenses_total)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-2">{t("truck.glance.kilos")}</dt>
          <dd className="text-lg font-bold">{formatQuantity((leftMillimes / 1000).toFixed(3))}</dd>
        </div>
      </dl>
      {waitingSales > 0 ? (
        <p className="text-sm text-ink-2">{t("truck.glance.waiting", { count: waitingSales })}</p>
      ) : null}
    </Card>
  );
}
