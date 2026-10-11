import { useGetMyTruckDay } from "@frutti/api";
import { useSession } from "@frutti/auth";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Card, EmptyState } from "@frutti/ui";

// "Ma journée": the truck of the day and what was loaded on it, in big plain lines.
export function DayPage() {
  const { t } = useTranslation();
  const session = useSession();
  const truck = session.data?.truck ?? null;
  const day = useGetMyTruckDay({ query: { enabled: truck !== null, retry: false } });

  if (truck === null) {
    return (
      <EmptyState illustration="truck" title={t("truck.day.noTruck")}>
        {t("truck.day.noTruckBody")}
      </EmptyState>
    );
  }
  const lines = day.data?.lines.filter((line) => Number(line.loaded) > 0) ?? [];
  return (
    <div className="space-y-4">
      <Card>
        <p className="text-sm text-muted">{t("truck.day.yourTruck")}</p>
        <p className="text-2xl font-bold">{truck.name}</p>
        <p className="text-muted">{truck.plate}</p>
      </Card>
      {day.isLoading ? null : lines.length === 0 ? (
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
                <span className="text-right">
                  <span className="block text-xl font-bold">{formatQuantity(line.loaded)} kg</span>
                  {line.unit_price === null ? null : (
                    <span className="text-sm text-muted">{formatMoney(line.unit_price)} / kg</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
