import { useGetPartnerReport } from "@frutti/api";
import { formatMoney, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState, Field, Input, Table, Td, Th } from "@frutti/ui";
import { useId, useState } from "react";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => `${today().slice(0, 8)}01`;

/** The "Partenaires" tab: capital and profit share per partner over a period (P7-T05, D-117). */
export function PartnerReports() {
  const { t } = useTranslation();
  const fromId = useId();
  const toId = useId();
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const query = { date_from: from, date_to: to };
  const report = useGetPartnerReport(query);
  const data = report.data;
  const search = new URLSearchParams(query).toString();
  return (
    <>
      <Card className="filter-bar flex flex-wrap items-end gap-3 p-3">
        <Field label={t("admin.reports.from")} htmlFor={fromId}>
          <Input id={fromId} type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label={t("admin.reports.to")} htmlFor={toId}>
          <Input id={toId} type="date" value={to} min={from} onChange={(event) => setTo(event.target.value)} />
        </Field>
        <Button asChild>
          <a href={`/api/v1/reports/partners/export?${search}`} download>
            {t("admin.reports.excel")}
          </a>
        </Button>
      </Card>
      {report.isPending && <p className="text-ink-2">{t("common.loading")}</p>}
      {report.isError && (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      )}
      {data &&
        (data.rows.length === 0 ? (
          <EmptyState illustration="mussel" title={t("admin.reports.empty")}>
            {t("admin.reports.partners.emptyBody")}
          </EmptyState>
        ) : (
          <Card className="p-2">
            <Table>
              <thead>
                <tr>
                  <Th rowSpan={2}>{t("admin.reports.partners.partner")}</Th>
                  <Th rowSpan={2} className="text-end">
                    {t("admin.reports.partners.lots")}
                  </Th>
                  <Th colSpan={4} className="text-center">
                    {t("admin.reports.partners.capital")}
                  </Th>
                  <Th colSpan={5} className="text-center">
                    {t("admin.reports.partners.share")}
                  </Th>
                </tr>
                <tr>
                  <Th className="text-end">{t("admin.reports.partners.contributed")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.lossDeducted")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.returned")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.outstanding")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.earned")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.uncovered")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.late")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.paid")}</Th>
                  <Th className="text-end">{t("admin.reports.partners.due")}</Th>
                </tr>
              </thead>
              <tbody>
                {[...data.rows, { ...data.totals, partner_id: 0, name: t("admin.reports.total") }].map((row) => (
                  <tr key={row.partner_id} className={row.partner_id === 0 ? "font-bold" : undefined}>
                    <Td>{row.name}</Td>
                    <Td className="num text-end">{row.lots}</Td>
                    <Td className="num text-end">{formatMoney(row.contributed)}</Td>
                    <Td className="num text-end">{formatMoney(row.loss_deducted)}</Td>
                    <Td className="num text-end">{formatMoney(row.returned)}</Td>
                    <Td className="num text-end">{formatMoney(row.capital_outstanding)}</Td>
                    <Td className="num text-end">{formatMoney(row.share)}</Td>
                    <Td className="num text-end">{formatMoney(row.uncovered_loss)}</Td>
                    <Td className="num text-end">{formatMoney(row.late_adjustments)}</Td>
                    <Td className="num text-end">{formatMoney(row.paid)}</Td>
                    <Td className="num text-end">{formatMoney(row.share_due)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        ))}
      <p className="text-[0.85rem] text-ink-2">{t("admin.reports.partners.note")}</p>
    </>
  );
}
