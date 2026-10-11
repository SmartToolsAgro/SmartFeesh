import { type LotCostLine, useGetLotCosts } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Button, Card, Pill, Table, Td, Th } from "@frutti/ui";
import { Link, useNavigate } from "react-router";

import { monthLabel } from "../hr/shared";
import { canWriteExpenses, EXPENSE_TONES } from "./shared";

/** A lot's costs so far: expenses typed on it, day labour, and its share of the truck costs of each day it
 * was loaded (by kg). Only approved lines count in the total; the lot result itself comes in Phase 6. */
export function LotCostsCard({ batchId, session }: { batchId: number; session: Session }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const costs = useGetLotCosts({ batch: batchId });
  const canWrite = canWriteExpenses(session);
  const how = (line: LotCostLine): string => {
    const month = line.month ? monthLabel(line.month, i18n.language) : "";
    switch (line.kind) {
      case "truck_day":
        return t("admin.lotCosts.truckShare", {
          truck: line.truck_name,
          quantity: formatQuantity(line.quantity ?? "0"),
          total: formatQuantity(line.day_quantity ?? "0"),
          amount: formatMoney(line.expense_amount),
        });
      case "cold_room":
        return t("admin.lotCosts.coldRoom", {
          room: line.location_name,
          kgDays: formatQuantity(line.quantity ?? "0"),
          month,
        });
      case "cold_room_adjustment":
        return t("admin.lotCosts.coldRoomAdjustment", { room: line.location_name, month });
      case "general":
        return t("admin.lotCosts.general", {
          kgDays: formatQuantity(line.quantity ?? "0"),
          amount: formatMoney(line.expense_amount),
          month,
        });
      default:
        return t("admin.lotCosts.onLot");
    }
  };

  return (
    <section aria-labelledby="lot-costs" className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="lot-costs" className="me-auto">
          {t("admin.lotCosts.title")}
        </h2>
        {canWrite && (
          <>
            <Button onClick={() => void navigate(`/charges/calendrier?lot=${batchId}`)}>
              {t("admin.lotCosts.addDay")}
            </Button>
            <Button onClick={() => void navigate(`/charges/nouvelle?lot=${batchId}`)}>
              {t("admin.lotCosts.addExpense")}
            </Button>
          </>
        )}
      </div>
      <Card className="p-2">
        {costs.isPending ? (
          <p className="p-2 text-ink-2">{t("common.loading")}</p>
        ) : !costs.data ? (
          <p role="alert" className="p-2 text-bad">
            {t("common.serverUnreachable")}
          </p>
        ) : costs.data.lines.length === 0 ? (
          <p className="p-2 text-ink-2">{t("admin.lotCosts.empty")}</p>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.lotCosts.columns.date")}</Th>
                  <Th>{t("admin.lotCosts.columns.cost")}</Th>
                  <Th className="max-[720px]:hidden">{t("admin.lotCosts.columns.how")}</Th>
                  <Th numeric>{t("admin.lotCosts.columns.amount")}</Th>
                </tr>
              </thead>
              <tbody>
                {costs.data.lines.map((line) => (
                  <tr key={`${line.kind}-${line.expense_id ?? "estimate"}-${line.month ?? ""}-${line.location_name}`}>
                    <Td className="num whitespace-nowrap">{formatDate(line.spent_on)}</Td>
                    <Td>
                      {line.expense_id !== null && (line.kind === "lot" || line.kind === "truck_day") ? (
                        <Link to={`/charges/${line.expense_id}`} className="font-semibold text-sea hover:underline">
                          {line.category_name}
                        </Link>
                      ) : (
                        <span className="font-semibold">{t(`admin.lotCosts.kinds.${line.kind}`)}</span>
                      )}
                      {line.description && <span className="text-ink-2"> · {line.description}</span>}
                      {line.status !== "approved" && (
                        <Pill className="ms-2" tone={EXPENSE_TONES[line.status]}>
                          {t(`admin.expenses.statuses.${line.status}`)}
                        </Pill>
                      )}
                      {line.estimated && (
                        <Pill className="ms-2" tone="warn" title={t("admin.lotCosts.estimatedHint")}>
                          {t("admin.lotCosts.estimated")}
                        </Pill>
                      )}
                      {line.kind === "cold_room_adjustment" && (
                        <Pill className="ms-2" tone="neutral">
                          {t("admin.lotCosts.correction")}
                        </Pill>
                      )}
                    </Td>
                    <Td className="max-[720px]:hidden text-[0.85rem] text-ink-2">{how(line)}</Td>
                    <Td numeric className="whitespace-nowrap">
                      {formatMoney(line.amount)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="flex justify-end gap-2 border-t border-line px-2.5 py-3">
              {t("admin.lotCosts.total")} <b className="num">{formatMoney(costs.data.total)}</b>
            </p>
          </>
        )}
      </Card>
    </section>
  );
}
