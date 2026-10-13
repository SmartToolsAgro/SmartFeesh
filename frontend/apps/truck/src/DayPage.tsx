import {
  type MyBoxDay,
  useAssignTruck,
  useGetMyBoxDay,
  useGetMyDay,
  useGetMyTruckDay,
  useListMyDays,
  useListMyStock,
  useListMyTruckChoices,
  useOpenMyDay,
} from "@frutti/api";
import { useSession } from "@frutti/auth";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState, Field, Input, toast } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { formatBoxCount } from "./boxes";

// "Ma journée", three steps and nothing else: pick the truck, check the load, start the day.
export function DayPage() {
  const session = useSession();
  const truck = session.data?.truck ?? null;
  return truck === null ? <PickTruck /> : <TruckDay truck={truck} />;
}

function PickTruck() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const choices = useListMyTruckChoices();
  const assign = useAssignTruck({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries(),
      onError: () => toast.error(t("truck.day.pickFailed")),
    },
  });
  const trucks = choices.data ?? [];
  if (choices.isLoading) return null;
  if (trucks.length === 0) {
    return (
      <EmptyState illustration="truck" title={t("truck.day.noTruck")}>
        {t("truck.day.noTruckBody")}
      </EmptyState>
    );
  }
  return (
    <div className="space-y-3">
      <h2>{t("truck.day.pickTruck")}</h2>
      {trucks.map((truck) => (
        <Button
          key={truck.id}
          size="lg"
          variant={truck.taken ? "ghost" : "primary"}
          className="flex-col py-5 text-xl"
          disabled={truck.taken || assign.isPending}
          onClick={() => assign.mutate({ data: { truck: truck.id } })}
        >
          <span>{truck.name}</span>
          <span className="text-sm font-normal">{truck.taken ? t("truck.day.taken") : truck.plate}</span>
        </Button>
      ))}
    </div>
  );
}

// The boxes of today per box type: what came, what the clients kept, what came back, and what should be on the truck.
function BoxDayCard({ day }: { day: MyBoxDay }) {
  const { t } = useTranslation();
  return (
    <Card>
      <h2 className="mb-3">{t("truck.boxes.dayTitle")}</h2>
      <ul className="divide-y divide-line">
        {day.lines.map((line) => (
          <li key={line.box_type} className="space-y-1 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-lg font-semibold">
                {line.box_type === "small" ? t("truck.boxes.small") : t("truck.boxes.big")}
              </span>
              <span className="font-bold">{t("truck.boxes.expected", { count: formatBoxCount(line.expected) })}</span>
            </div>
            <p className="text-sm text-ink-2">
              {t("truck.boxes.dayLine", {
                loaded: formatBoxCount(line.loaded),
                left: formatBoxCount(line.left),
                collected: formatBoxCount(line.collected),
              })}
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function TruckDay({ truck }: { truck: { name: string; plate: string } }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [cash, setCash] = useState("0");
  const day = useGetMyDay({ query: { retry: false } });
  const load = useGetMyTruckDay({ query: { retry: false } });
  const open = useOpenMyDay({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries(),
      onError: () => toast.error(t("truck.day.startFailed")),
    },
  });
  // Kilos left on the truck from an earlier day are not in today's load: show them as "in the truck".
  const stock = useListMyStock({ query: { retry: false } });
  // Returnable boxes of the truck today (P1-T14d): read only, nothing is posted at closing.
  const boxes = useGetMyBoxDay({ query: { retry: false } });
  const loadedToday = load.data?.lines.filter((line) => Number(line.loaded) > 0) ?? [];
  const lines =
    loadedToday.length > 0
      ? loadedToday.map((line) => ({ ...line, quantity: line.loaded }))
      : (stock.data ?? []).filter((line) => Number(line.quantity) > 0);
  const running = day.data !== undefined && day.data.ended_at === null;
  // The day's closing was sent: the driver may start another one the same date (D-134).
  const ended = day.data !== undefined && day.data.ended_at !== null;
  const cashValue = parseDecimalInput(cash.trim(), 3);
  // A day the office asked about waits in the history for the driver's answer.
  const days = useListMyDays({ query: { retry: false } });
  const asked = days.data?.find((row) => row.closing?.status === "justification");

  return (
    <div className="space-y-4">
      {asked === undefined ? null : (
        <Link to={`/historique/${asked.id}`} className="block">
          <Card className="space-y-1">
            <p className="font-semibold text-bad">{t("truck.history.askedTitle")}</p>
            <p>{t("truck.closing.asked", { reason: asked.closing?.review_note ?? "" })}</p>
          </Card>
        </Link>
      )}
      <Card>
        <p className="text-sm text-ink-2">{t("truck.day.yourTruck")}</p>
        <p className="text-2xl font-bold">{truck.name}</p>
        <p className="text-ink-2">{truck.plate}</p>
      </Card>
      {load.isLoading || stock.isLoading ? null : lines.length === 0 ? (
        <EmptyState illustration="fridge" title={t("truck.day.nothingLoaded")}>
          {t("truck.day.nothingLoadedBody")}
        </EmptyState>
      ) : (
        <Card>
          <h2 className="mb-3">{t(loadedToday.length > 0 ? "truck.day.loaded" : "truck.day.inTruck")}</h2>
          <ul className="divide-y divide-line">
            {lines.map((line) => (
              <li key={line.product_id} className="flex items-center justify-between gap-3 py-3">
                <span className="text-lg font-semibold">{line.product_name}</span>
                <span className="text-end">
                  <span className="block text-xl font-bold">{formatQuantity(line.quantity)}</span>
                  {line.unit_price === null ? null : (
                    <span className="text-sm text-ink-2">{formatMoney(line.unit_price)} / kg</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {boxes.data === undefined ? null : <BoxDayCard day={boxes.data} />}
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/reprise">{t("truck.boxes.pickupAdd")}</Link>
      </Button>
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/depense">{t("truck.expense.add")}</Link>
      </Button>
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/encaissement">{t("truck.payment.add")}</Link>
      </Button>
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/perte">{t("truck.loss.add")}</Link>
      </Button>
      {day.isLoading ? null : running ? (
        <Card>
          <p className="text-lg font-semibold">
            {day.data.number > 1
              ? t("truck.history.startedNumber", { number: day.data.number })
              : t("truck.day.started")}
          </p>
          <p className="text-ink-2">{t("truck.day.cashAtStart", { amount: formatMoney(day.data.opening_cash) })}</p>
        </Card>
      ) : (
        <Card className="space-y-3">
          {ended ? (
            <div>
              <p className="text-lg font-semibold">{t("truck.history.ended")}</p>
              <p className="text-ink-2">{t("truck.history.endedBody")}</p>
            </div>
          ) : null}
          <Field label={t("truck.day.cashLabel")} htmlFor="opening-cash">
            <Input
              id="opening-cash"
              inputMode="decimal"
              className="text-xl"
              value={cash}
              onChange={(event) => setCash(event.target.value)}
            />
          </Field>
          <Button
            size="lg"
            variant="primary"
            className="py-4 text-lg"
            disabled={cashValue === null || open.isPending}
            onClick={() => cashValue !== null && open.mutate({ data: { opening_cash: cashValue } })}
          >
            {t(ended ? "truck.history.startAnother" : "truck.day.start")}
          </Button>
        </Card>
      )}
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/historique">{t("truck.history.open")}</Link>
      </Button>
    </div>
  );
}
