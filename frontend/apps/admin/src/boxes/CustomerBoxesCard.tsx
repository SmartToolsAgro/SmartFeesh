import { useListBoxBalances } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Card, CardTitle } from "@frutti/ui";
import { useMemo } from "react";

import { customerBoxCounts, formatBoxCount, holdersFromBalances } from "./shared";

/** The client page's "Caisses chez le client": how many boxes of each type the client holds (read only). */
export function CustomerBoxesCard({ customerName }: { customerName: string }) {
  const { t } = useTranslation();
  const balances = useListBoxBalances();
  const counts = useMemo(
    () => (balances.data ? customerBoxCounts(holdersFromBalances(balances.data), customerName) : null),
    [balances.data, customerName],
  );

  return (
    <Card className="col-span-full">
      <CardTitle>{t("admin.boxes.customer.title")}</CardTitle>
      {balances.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : !counts ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:max-w-md">
            <div>
              <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.boxes.types.small")}</dt>
              <dd className="num text-[1.4rem] font-bold" data-testid="customer-small-boxes">
                {formatBoxCount(counts.small)}
              </dd>
            </div>
            <div>
              <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.boxes.types.big")}</dt>
              <dd className="num text-[1.4rem] font-bold" data-testid="customer-big-boxes">
                {formatBoxCount(counts.big)}
              </dd>
            </div>
          </dl>
          {counts.ambiguous && <p className="mt-3 text-warn">{t("admin.boxes.customer.ambiguous")}</p>}
        </>
      )}
    </Card>
  );
}
