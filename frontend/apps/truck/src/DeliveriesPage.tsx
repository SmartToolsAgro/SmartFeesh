import { useConfirmSale, useListMyDeliveries, type SaleDetail } from "@frutti/api";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { formatBoxCount } from "./boxes";
import { FoldCard } from "./FoldCard";
import { sendError } from "./sendError";

// "Mes livraisons": the BL the office prepared with the truck's load, one per client (D-160). Delivering one confirms
// it: the kilos leave the truck, the client owes the amount and the boxes are counted to them. Each delivery opens on
// tap, so the list shows every client on one screen (D-168).
export function DeliveriesPage() {
  const { t } = useTranslation();
  const deliveries = useListMyDeliveries({ query: { retry: false } });

  if (deliveries.isPending) return <Card className="h-24 animate-pulse" aria-busy="true" />;
  if (deliveries.isError) {
    return (
      <Card className="space-y-3">
        <p className="text-lg font-semibold">{t("truck.deliveries.failed")}</p>
        <Button size="lg" onClick={() => void deliveries.refetch()}>
          {t("truck.stock.retry")}
        </Button>
      </Card>
    );
  }
  if (deliveries.data.length === 0) {
    return (
      <EmptyState illustration="truck" title={t("truck.deliveries.empty")}>
        {t("truck.deliveries.emptyBody")}
      </EmptyState>
    );
  }
  return (
    <div className="space-y-3">
      <h2>{t("truck.deliveries.title")}</h2>
      {deliveries.data.map((sale) => (
        <Delivery key={sale.id} sale={sale} />
      ))}
    </div>
  );
}

function Delivery({ sale }: { sale: SaleDetail }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const confirm = useConfirmSale({
    mutation: {
      onSuccess: () => {
        setError("");
        void queryClient.invalidateQueries();
      },
      onError: (failure) => setError(sendError(failure, t("truck.deliveries.failedConfirm"))),
    },
  });
  const boxes = (["small", "big"] as const).filter((type) => (sale.boxes[type] ?? 0) > 0);

  return (
    <FoldCard
      title={sale.customer.name}
      summary={t("truck.deliveries.summary", { count: sale.lines.length, total: formatMoney(sale.total) })}
    >
      <div className="space-y-3">
        {sale.delivery_address ? <p className="text-ink-2">{sale.delivery_address}</p> : null}
        <ul className="divide-y divide-line">
          {sale.lines.map((line) => (
            <li key={line.id} className="flex items-center justify-between gap-3 py-2">
              <span className="text-lg font-semibold">{line.product.name}</span>
              <span className="text-right">
                <span className="block text-lg font-bold">{formatQuantity(line.quantity)}</span>
                <span className="text-sm text-ink-2">{formatMoney(line.unit_price)} / kg</span>
              </span>
            </li>
          ))}
        </ul>
        {boxes.length > 0 ? (
          <p>
            {boxes
              .map(
                (type) =>
                  `${t(type === "small" ? "truck.boxes.small" : "truck.boxes.big")} : ${formatBoxCount(sale.boxes[type] ?? 0)}`,
              )
              .join(" · ")}
          </p>
        ) : null}
        <p className="flex justify-between text-lg font-bold">
          <span>{t("truck.deliveries.total")}</span>
          <span>{formatMoney(sale.total)}</span>
        </p>
        {error ? (
          <p role="alert" className="font-semibold text-bad">
            {error}
          </p>
        ) : null}
        <Button
          size="lg"
          variant="primary"
          className="w-full py-4 text-lg"
          disabled={confirm.isPending || !navigator.onLine}
          onClick={() => confirm.mutate({ saleId: sale.id, data: {} })}
        >
          {confirm.isPending ? t("truck.deliveries.confirming") : t("truck.deliveries.confirm")}
        </Button>
        {navigator.onLine ? null : <p className="text-sm text-ink-2">{t("truck.deliveries.offline")}</p>}
      </div>
    </FoldCard>
  );
}
