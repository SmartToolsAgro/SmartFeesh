import type { DayProduct, DaySummary, MyDaySummary } from "@frutti/api";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, Input } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { closingGate } from "./closingGate";
import { useOnline } from "./offline";
import { useQueue } from "./queue";
import { sendWaiting, useSyncProblem } from "./sync";

const millimes = (value: string) => Math.round(Number(value) * 1000);

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <p className={`flex items-baseline justify-between gap-3 ${strong ? "text-xl font-bold" : ""}`}>
      <span>{label}</span>
      <span>{value}</span>
    </p>
  );
}

/** The opening stock and the gap of a product (D-130). A day sent before they existed is shown as it was sent,
 * without them: its kept figures do not have them. */
function stockOf(product: DayProduct): { opening?: string; unexplained?: string } {
  const kept: Partial<Pick<DayProduct, "opening" | "unexplained">> = product;
  return { opening: kept.opening, unexplained: kept.unexplained };
}

/** The cash counted at the sends a new load undid: it is with the office (D-134). A day sent before the figure
 * existed has none in its kept figures. */
function handedOverOf(summary: DaySummary): string | null {
  const kept: Partial<Pick<DaySummary, "handed_over">> = summary;
  return kept.handed_over !== undefined && Number(kept.handed_over) !== 0 ? kept.handed_over : null;
}

function Figures({ summary }: { summary: DaySummary }) {
  const { t } = useTranslation();
  const handedOver = handedOverOf(summary);
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
        {handedOver === null ? null : <Row label={t("truck.closing.handedOver")} value={formatMoney(handedOver)} />}
        <Row label={t("truck.closing.expected")} value={formatMoney(summary.expected_cash)} strong />
      </Card>
      {summary.products.length === 0 ? null : (
        <Card>
          <h2 className="mb-3">{t("truck.closing.stock")}</h2>
          <ul className="divide-y divide-line">
            {summary.products.map((product) => {
              const { opening, unexplained } = stockOf(product);
              return (
                <li key={product.product_id} className="space-y-1 py-3">
                  <p className="text-lg font-semibold">{product.product_name}</p>
                  <p className="text-sm text-ink-2">
                    {opening === undefined ? null : `${t("truck.closing.stockOpening")} ${formatQuantity(opening)} · `}
                    {t("truck.closing.loaded")} {formatQuantity(product.loaded)} · {t("truck.closing.sold")}{" "}
                    {formatQuantity(product.sold)} · {t("truck.closing.lost")} {formatQuantity(product.lost)} ·{" "}
                    {t("truck.closing.returned")} {formatQuantity(product.returned)}
                  </p>
                  <p className="font-semibold">
                    {t("truck.closing.left")} {formatQuantity(product.remaining)}
                  </p>
                  {unexplained === undefined || Number(unexplained) === 0 ? null : (
                    <p className="font-semibold text-bad">
                      {t("truck.closing.unexplained", { kg: formatQuantity(unexplained) })}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </Card>
      )}
    </>
  );
}

/** A driver's day in a few lines, its closing state, and the form to send it while it can be sent: the "Clôture"
 * screen for the day of now, the history for an earlier one (D-134). Both wait for what the phone still has to
 * send, say why it waits and let the driver retry (D-129). A sent day is sent again when the office asked, when
 * a new load reopened it, or when its records changed since the send (D-132). */
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
  const queryClient = useQueryClient();
  const queue = useQueue();
  const online = useOnline();
  const problem = useSyncProblem();
  const [retrying, setRetrying] = useState(false);
  const [counted, setCounted] = useState("");
  const [note, setNote] = useState("");
  // Waiting sales are sent as soon as the day's figures open, not only on the half-minute timer (D-090).
  useEffect(() => {
    void sendWaiting(queryClient);
  }, [queryClient]);
  const retry = async () => {
    setRetrying(true);
    try {
      await sendWaiting(queryClient);
    } finally {
      setRetrying(false);
    }
  };
  const { summary, closing } = data;
  const changed = closing?.status === "submitted" && closing.changed_since_sent;
  const locked = closing?.status === "approved" || (closing?.status === "submitted" && !changed);
  const handedOver = handedOverOf(summary);
  const countedValue = parseDecimalInput(counted.trim(), 3);
  const gap = countedValue === null ? null : (millimes(countedValue) - millimes(summary.expected_cash)) / 1000;
  const gate = closingGate({ queue, online, countedReady: countedValue !== null, busy: sending });
  const waiting = gate.waiting;
  // Why the sale has not gone yet: the phone's own connection first, then what the last send ran into.
  const waitReason = !online
    ? t("truck.closing.waitOffline")
    : problem === "session"
      ? t("truck.closing.waitSession")
      : problem === "server"
        ? t("truck.closing.waitServerBusy")
        : problem === "offline"
          ? t("truck.closing.waitNoAnswer")
          : t("truck.closing.waitRetrying");

  return (
    <div className="space-y-4">
      <Figures summary={summary} />
      {closing?.status === "approved" ? (
        <Card>
          <p className="text-xl font-bold">{t("truck.closing.approved")}</p>
          <p className="text-ink-2">{t("truck.closing.countedWas", { amount: formatMoney(closing.counted_cash) })}</p>
        </Card>
      ) : closing?.status === "submitted" && !changed ? (
        <Card>
          <p className="text-xl font-bold">{t("truck.closing.sent")}</p>
          <p className="text-ink-2">{t("truck.closing.countedWas", { amount: formatMoney(closing.counted_cash) })}</p>
        </Card>
      ) : null}
      {locked ? null : (
        <Card className="space-y-4">
          {closing?.status === "reopened" ? (
            <p className="font-semibold text-warn">{t("truck.closing.reopened")}</p>
          ) : null}
          {changed ? <p className="font-semibold text-warn">{t("truck.closing.changed")}</p> : null}
          {closing !== null && closing.status !== "submitted" && closing.review_note !== "" ? (
            <p className="font-semibold text-bad">{t("truck.closing.asked", { reason: closing.review_note })}</p>
          ) : null}
          {handedOver === null ? null : (
            <p className="text-ink-2">{t("truck.closing.handedOverHint", { amount: formatMoney(handedOver) })}</p>
          )}
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
            <div className="space-y-2">
              <p className="font-semibold text-warn">{t("truck.closing.waitingSales", { count: waiting })}</p>
              <p className="text-ink-2">{waitReason}</p>
              <Button disabled={!online || retrying} onClick={() => void retry()}>
                {t("truck.closing.retrySend")}
              </Button>
            </div>
          ) : !online ? (
            <p className="text-warn">{t("truck.closing.needNetwork")}</p>
          ) : null}
          <Button
            size="lg"
            variant="primary"
            className="py-4 text-lg"
            disabled={!gate.canSend}
            onClick={() => countedValue !== null && onSend(countedValue, note)}
          >
            {t("truck.closing.send")}
          </Button>
        </Card>
      )}
    </div>
  );
}
