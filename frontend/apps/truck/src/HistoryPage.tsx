import { type MyDayRow, useCloseMyPastDay, useGetMyPastDay, useListMyDays } from "@frutti/api";
import { formatDate, formatMoney, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { DayReport } from "./DayReport";
import { sendError } from "./sendError";

const TONES = { submitted: "text-warn", justification: "text-bad", approved: "text-good" } as const;

function signed(value: string): string {
  return `${Number(value) > 0 ? "+" : ""}${formatMoney(value)}`;
}

/** "Journée 2 · 13/10/2026", or just the date when it was the only day of that date. */
function useDayTitle() {
  const { t } = useTranslation();
  return (row: { date: string; number: number }) =>
    row.number > 1
      ? t("truck.history.dayNumber", { number: row.number, date: formatDate(row.date) })
      : formatDate(row.date);
}

function DayStatus({ row }: { row: MyDayRow }) {
  const { t } = useTranslation();
  if (row.closing === null) {
    return (
      <span className="text-ink-2">{t(row.ended_at === null ? "truck.history.running" : "truck.history.notSent")}</span>
    );
  }
  return (
    <span className={`font-semibold ${TONES[row.closing.status]}`}>
      {t(`truck.history.statuses.${row.closing.status}`)}
    </span>
  );
}

// "Mes journées": the driver's days, newest first; one tap opens its figures (D-126).
export function HistoryPage() {
  const { t } = useTranslation();
  const days = useListMyDays({ query: { retry: false } });
  const title = useDayTitle();
  if (days.isLoading) return null;
  const rows = days.data ?? [];
  if (rows.length === 0) {
    return (
      <EmptyState illustration="truck" title={t("truck.history.empty")}>
        {t("truck.history.emptyBody")}
      </EmptyState>
    );
  }
  return (
    <div className="space-y-3">
      <h2>{t("truck.history.title")}</h2>
      {rows.map((row) => (
        <Link key={row.id} to={`/historique/${row.id}`} className="block">
          <Card className="space-y-1">
            <p className="flex items-baseline justify-between gap-3">
              <span className="text-lg font-bold">{title(row)}</span>
              <DayStatus row={row} />
            </p>
            <p className="text-sm text-ink-2">{row.truck_name}</p>
            {row.closing === null ? null : (
              <p className="flex justify-between gap-3">
                <span>{t("truck.history.counted", { amount: formatMoney(row.closing.counted_cash) })}</span>
                <span className="font-semibold">
                  {t("truck.history.gap", { amount: signed(row.closing.difference) })}
                </span>
              </p>
            )}
          </Card>
        </Link>
      ))}
    </div>
  );
}

// One day of the history: its figures as sent, and the form when the office asked for a justification or the day
// was never sent.
export function HistoryDayPage() {
  const { t } = useTranslation();
  const { dayId } = useParams();
  const id = Number(dayId);
  const queryClient = useQueryClient();
  const day = useGetMyPastDay(id, { query: { retry: false, enabled: Number.isInteger(id) } });
  const days = useListMyDays({ query: { retry: false } });
  const title = useDayTitle();
  const [error, setError] = useState("");
  const send = useCloseMyPastDay({
    mutation: {
      onSuccess: () => {
        setError("");
        void queryClient.invalidateQueries();
      },
      onError: (failure) => setError(sendError(failure, t("truck.closing.failed"))),
    },
  });
  const row = days.data?.find((item) => item.id === id);
  return (
    <div className="space-y-4">
      <Button asChild className="self-start">
        <Link to="/historique">{t("truck.history.back")}</Link>
      </Button>
      {row === undefined ? null : (
        <div>
          <h2>{title(row)}</h2>
          <p className="text-ink-2">{row.truck_name}</p>
        </div>
      )}
      {day.isLoading ? null : day.data === undefined ? (
        <p className="text-bad">{t("truck.history.failed")}</p>
      ) : (
        <DayReport
          data={day.data}
          sending={send.isPending}
          error={error}
          onSend={(counted, note) => send.mutate({ dayId: id, data: { counted_cash: counted, note } })}
        />
      )}
    </div>
  );
}
