import { useAssignTruck, useGetMyDay, useGetMyTruckDay, useListMyTruckChoices, useOpenMyDay } from "@frutti/api";
import { useSession } from "@frutti/auth";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState, Field, Input, toast } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

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
  const lines = load.data?.lines.filter((line) => Number(line.loaded) > 0) ?? [];
  const started = day.data !== undefined;
  const cashValue = parseDecimalInput(cash.trim(), 3);

  return (
    <div className="space-y-4">
      <Card>
        <p className="text-sm text-ink-2">{t("truck.day.yourTruck")}</p>
        <p className="text-2xl font-bold">{truck.name}</p>
        <p className="text-ink-2">{truck.plate}</p>
      </Card>
      {load.isLoading ? null : lines.length === 0 ? (
        <EmptyState illustration="fridge" title={t("truck.day.nothingLoaded")}>
          {t("truck.day.nothingLoadedBody")}
        </EmptyState>
      ) : (
        <Card>
          <h2 className="mb-3">{t("truck.day.loaded")}</h2>
          <ul className="divide-y divide-line">
            {lines.map((line) => (
              <li key={line.product_id} className="flex items-center justify-between gap-3 py-3">
                <span className="text-lg font-semibold">{line.product_name}</span>
                <span className="text-end">
                  <span className="block text-xl font-bold">{formatQuantity(line.loaded)} kg</span>
                  {line.unit_price === null ? null : (
                    <span className="text-sm text-ink-2">{formatMoney(line.unit_price)} / kg</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/depense">{t("truck.expense.add")}</Link>
      </Button>
      <Button asChild size="lg" className="py-4 text-lg">
        <Link to="/perte">{t("truck.loss.add")}</Link>
      </Button>
      {day.isLoading ? null : started ? (
        <Card>
          <p className="text-lg font-semibold">{t("truck.day.started")}</p>
          <p className="text-ink-2">{t("truck.day.cashAtStart", { amount: formatMoney(day.data.opening_cash) })}</p>
        </Card>
      ) : (
        <Card className="space-y-3">
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
            {t("truck.day.start")}
          </Button>
        </Card>
      )}
    </div>
  );
}
