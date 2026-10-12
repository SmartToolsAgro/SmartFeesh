import { ApiError, useCloseMyDay, useGetMyDaySummary } from "@frutti/api";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState, Input } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { useQueue } from "./queue";
import { useOnline } from "./offline";

const millimes = (value: string) => Math.round(Number(value) * 1000);

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <p className={`flex items-baseline justify-between gap-3 ${strong ? "text-xl font-bold" : ""}`}>
      <span>{label}</span>
      <span>{value}</span>
    </p>
  );
}

// "Clôture": the day in a few lines, the cash counted, and one button to send it to the office.
export function ClosingPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const day = useGetMyDaySummary({ query: { retry: false } });
  const queue = useQueue();
  const online = useOnline();
  const waiting = queue.filter((item) => item.status === "pending").length;
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const send = useCloseMyDay({
    mutation: {
      onSuccess: () => {
        setError("");
        void queryClient.invalidateQueries();
      },
      onError: (failure) => {
        const body = failure instanceof ApiError ? JSON.stringify(failure.body ?? "") : "";
        setError(body === "" || body === '""' ? t("truck.closing.failed") : body);
      },
    },
  });

  if (day.isLoading) return null;
  if (day.data === undefined) {
    return (
      <EmptyState illustration="fridge" title={t("truck.closing.notStarted")}>
        {t("truck.closing.notStartedBody")}
      </EmptyState>
    );
  }
  const { summary, closing } = day.data;
  const locked = closing?.status === "submitted" || closing?.status === "approved";
  const countedValue = parseDecimalInput(counted.trim(), 3);
  const gap = countedValue === null ? null : (millimes(countedValue) - millimes(summary.expected_cash)) / 1000;

  return (
    <div className="space-y-4">
      <Card className="space-y-2">
        <h2>{t("truck.closing.title")}</h2>
        <Row
          label={t("truck.closing.sales", { count: summary.sales_count })}
          value={formatMoney(summary.sales_total)}
          strong
        />
        <Row label={t("truck.closing.cash")} value={formatMoney(summary.cash_received)} />
        <Row label={t("truck.closing.payments")} value={formatMoney(summary.payments_cash ?? "0.000")} />
        <Row label={t("truck.closing.other")} value={formatMoney(summary.other_payments)} />
        <Row label={t("truck.closing.credit")} value={formatMoney(summary.on_credit)} />
        <Row label={t("truck.closing.expenses")} value={formatMoney(summary.expenses_total)} />
        <Row label={t("truck.closing.opening")} value={formatMoney(summary.opening_cash)} />
        <Row label={t("truck.closing.expected")} value={formatMoney(summary.expected_cash)} strong />
      </Card>
      {summary.products.length === 0 ? null : (
        <Card>
          <h2 className="mb-3">{t("truck.closing.stock")}</h2>
          <ul className="divide-y divide-line">
            {summary.products.map((product) => (
              <li key={product.product_id} className="space-y-1 py-3">
                <p className="text-lg font-semibold">{product.product_name}</p>
                <p className="text-sm text-ink-2">
                  {t("truck.closing.loaded")} {formatQuantity(product.loaded)} · {t("truck.closing.sold")}{" "}
                  {formatQuantity(product.sold)} · {t("truck.closing.lost")} {formatQuantity(product.lost)} ·{" "}
                  {t("truck.closing.returned")} {formatQuantity(product.returned)}
                </p>
                <p className="font-semibold">
                  {t("truck.closing.left")} {formatQuantity(product.remaining)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {closing?.status === "approved" ? (
        <Card>
          <p className="text-xl font-bold">{t("truck.closing.approved")}</p>
        </Card>
      ) : closing?.status === "submitted" ? (
        <Card>
          <p className="text-xl font-bold">{t("truck.closing.sent")}</p>
          <p className="text-ink-2">{t("truck.closing.countedWas", { amount: formatMoney(closing.counted_cash) })}</p>
        </Card>
      ) : null}
      {locked ? null : (
        <Card className="space-y-4">
          {closing?.status === "justification" ? (
            <p className="font-semibold text-bad">{t("truck.closing.asked", { reason: closing.review_note })}</p>
          ) : null}
          <div className="space-y-1">
            <label htmlFor="counted-cash" className="font-semibold">
              {t("truck.closing.counted")}
            </label>
            <Input
              id="counted-cash"
              inputMode="decimal"
              placeholder="0"
              className="text-2xl"
              value={counted}
              onChange={(event) => setCounted(event.target.value)}
            />
          </div>
          {gap === null ? null : (
            <p className="text-lg font-semibold">
              {t("truck.closing.gap", { amount: `${gap > 0 ? "+" : ""}${formatMoney(gap.toFixed(3))}` })}
            </p>
          )}
          <div className="space-y-1">
            <label htmlFor="closing-note" className="font-semibold">
              {t("truck.closing.note")}
            </label>
            <Input id="closing-note" value={note} onChange={(event) => setNote(event.target.value)} />
          </div>
          {error === "" ? null : <p className="text-bad">{error}</p>}
          {waiting > 0 ? (
            <p className="text-warn">{t("truck.closing.sendFirst", { count: waiting })}</p>
          ) : !online ? (
            <p className="text-warn">{t("truck.closing.needNetwork")}</p>
          ) : null}
          <Button
            size="lg"
            variant="primary"
            className="py-4 text-lg"
            disabled={countedValue === null || send.isPending || !online || waiting > 0}
            onClick={() => countedValue !== null && send.mutate({ data: { counted_cash: countedValue, note } })}
          >
            {t("truck.closing.send")}
          </Button>
        </Card>
      )}
    </div>
  );
}
