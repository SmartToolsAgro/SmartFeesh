import type { DaySummary, MyDaySummary } from "@frutti/api";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, Input } from "@frutti/ui";
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

function Figures({ summary }: { summary: DaySummary }) {
  const { t } = useTranslation();
  return (
    <>
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
    </>
  );
}

/** A driver's day in a few lines, its closing state, and the form to send it while it can be sent: the "Clôture"
 * screen for the day of now, the history for an earlier one (D-126). */
export function DayReport({
  data,
  sending,
  error,
  onSend,
}: {
  data: MyDaySummary;
  sending: boolean;
  error: string;
  onSend: (counted: string, note: string) => void;
}) {
  const { t } = useTranslation();
  const queue = useQueue();
  const online = useOnline();
  const waiting = queue.filter((item) => item.status === "pending").length;
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  const { summary, closing } = data;
  const locked = closing?.status === "submitted" || closing?.status === "approved";
  const countedValue = parseDecimalInput(counted.trim(), 3);
  const gap = countedValue === null ? null : (millimes(countedValue) - millimes(summary.expected_cash)) / 1000;

  return (
    <div className="space-y-4">
      <Figures summary={summary} />
      {closing?.status === "approved" ? (
        <Card>
          <p className="text-xl font-bold">{t("truck.closing.approved")}</p>
          <p className="text-ink-2">{t("truck.closing.countedWas", { amount: formatMoney(closing.counted_cash) })}</p>
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
            disabled={countedValue === null || sending || !online || waiting > 0}
            onClick={() => countedValue !== null && onSend(countedValue, note)}
          >
            {t("truck.closing.send")}
          </Button>
        </Card>
      )}
    </div>
  );
}
