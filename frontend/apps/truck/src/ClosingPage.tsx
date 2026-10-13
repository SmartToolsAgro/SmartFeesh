import { useCloseMyDay, useGetMyDaySummary } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Button, EmptyState } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { DayReport } from "./DayReport";
import { sendError } from "./sendError";

// "Clôture": the day in a few lines, the cash counted, and one button to send it to the office (the figures, the
// wait for the phone's unsent sales and the form are in DayReport, shared with the history). Sending ends the day;
// the driver may then start another one from "Ma journée" (D-134).
export function ClosingPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const day = useGetMyDaySummary({ query: { retry: false } });
  const [error, setError] = useState("");
  const send = useCloseMyDay({
    mutation: {
      onSuccess: () => {
        setError("");
        void queryClient.invalidateQueries();
      },
      onError: (failure) => setError(sendError(failure, t("truck.closing.failed"))),
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
  const sent = day.data.closing !== null && day.data.closing.status !== "justification";
  return (
    <div className="space-y-4">
      <DayReport
        data={day.data}
        sending={send.isPending}
        error={error}
        onSend={(counted, note) => send.mutate({ data: { counted_cash: counted, note } })}
      />
      {sent ? (
        <Button asChild size="lg" variant="primary" className="py-4 text-lg">
          <Link to="/">{t("truck.history.startAnother")}</Link>
        </Button>
      ) : null}
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/historique">{t("truck.history.open")}</Link>
      </Button>
    </div>
  );
}
