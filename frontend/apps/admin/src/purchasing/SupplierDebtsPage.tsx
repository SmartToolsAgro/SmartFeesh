import { useGetSupplierDebts } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatMoney, useTranslation } from "@frutti/i18n";
import { Button, Card, CardTitle, cn, EmptyState, PageHeader, Pill, Table, Td, Th } from "@frutti/ui";
import type { ReactNode } from "react";
import { Link, useNavigate, useOutletContext } from "react-router";

import { canRecordReceipts, todayInTunis } from "../receipts/shared";
import { PurchasingTabs } from "./PurchasingTabs";

function Figure({ label, children, tone }: { label: string; children: ReactNode; tone?: "bad" | "warn" }) {
  return (
    <Card className="flex flex-col gap-1">
      <span className="text-[0.8rem] font-semibold text-ink-2">{label}</span>
      <span className={cn("num text-[1.3rem] font-bold", tone === "bad" && "text-bad", tone === "warn" && "text-warn")}>
        {children}
      </span>
    </Card>
  );
}

/** "Dettes fournisseurs" (D-159): what is owed to each supplier and when, and the cheques and traites to be cashed. */
export function SupplierDebtsPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const canPay = canRecordReceipts(session);
  const debts = useGetSupplierDebts();
  const today = todayInTunis();

  const header = (
    <>
      <PageHeader eyebrow={t("admin.nav.purchases")} title={t("admin.supplierDebts.title")} />
      <PurchasingTabs />
      <p className="text-ink-2">{t("admin.supplierDebts.intro")}</p>
    </>
  );
  if (debts.isPending)
    return (
      <>
        {header}
        <p className="text-ink-2">{t("common.loading")}</p>
      </>
    );
  if (!debts.data) {
    return (
      <>
        {header}
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      </>
    );
  }
  const data = debts.data;
  const pay = (supplierId: number) => void navigate(`/achats/paiements/nouveau?fournisseur=${supplierId}`);

  return (
    <>
      {header}
      <div className="grid grid-cols-4 gap-3 max-[900px]:grid-cols-2">
        <Figure label={t("admin.supplierDebts.totalOutstanding")}>{formatMoney(data.total_outstanding)}</Figure>
        <Figure label={t("admin.supplierDebts.totalOverdue")} tone={Number(data.total_overdue) > 0 ? "bad" : undefined}>
          {formatMoney(data.total_overdue)}
        </Figure>
        <Figure
          label={t("admin.supplierDebts.totalDueSoon")}
          tone={Number(data.total_due_soon) > 0 ? "warn" : undefined}
        >
          {formatMoney(data.total_due_soon)}
        </Figure>
        <Figure label={t("admin.supplierDebts.chequesTotal")}>{formatMoney(data.cheques_total)}</Figure>
      </div>

      {data.rows.length === 0 ? (
        <EmptyState illustration="fish" title={t("admin.supplierDebts.empty")}>
          {t("admin.supplierDebts.emptyBody")}
        </EmptyState>
      ) : (
        <Card className="p-2">
          <CardTitle className="px-2.5 pt-2">{t("admin.supplierDebts.bySupplier")}</CardTitle>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.supplierDebts.columns.supplier")}</Th>
                <Th numeric>{t("admin.supplierDebts.columns.outstanding")}</Th>
                <Th numeric>{t("admin.supplierDebts.columns.overdue")}</Th>
                <Th numeric className="max-[720px]:hidden">
                  {t("admin.supplierDebts.columns.dueSoon")}
                </Th>
                <Th className="max-[720px]:hidden">{t("admin.supplierDebts.columns.nextDue")}</Th>
                <Th numeric className="max-[720px]:hidden">
                  {t("admin.supplierDebts.columns.advances")}
                </Th>
                {canPay && <Th />}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.supplier_id}>
                  <Td>
                    <Link to={`/fournisseurs/${row.supplier_id}`} className="font-semibold hover:underline">
                      {row.name}
                    </Link>
                    <div className="text-[0.8rem] text-ink-2">
                      {t("admin.supplierDebts.invoices", { count: row.open_invoices })}
                    </div>
                  </Td>
                  <Td numeric className="font-semibold whitespace-nowrap">
                    {formatMoney(row.outstanding)}
                  </Td>
                  <Td numeric className={cn("whitespace-nowrap", Number(row.overdue) > 0 && "font-semibold text-bad")}>
                    {Number(row.overdue) > 0 ? formatMoney(row.overdue) : "—"}
                  </Td>
                  <Td
                    numeric
                    className={cn("whitespace-nowrap max-[720px]:hidden", Number(row.due_soon) > 0 && "text-warn")}
                  >
                    {Number(row.due_soon) > 0 ? formatMoney(row.due_soon) : "—"}
                  </Td>
                  <Td className="num whitespace-nowrap max-[720px]:hidden">
                    {row.next_due ? (
                      <>
                        {formatDate(row.next_due)}
                        {row.next_due < today && (
                          <Pill className="ms-2" tone="bad">
                            {t("admin.supplierDebts.late")}
                          </Pill>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </Td>
                  <Td numeric className="whitespace-nowrap max-[720px]:hidden">
                    {Number(row.advances) > 0 ? formatMoney(row.advances) : "—"}
                  </Td>
                  {canPay && (
                    <Td className="text-end">
                      {Number(row.outstanding) > 0 && (
                        <Button onClick={() => pay(row.supplier_id)}>{t("admin.supplierDebts.pay")}</Button>
                      )}
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      <Card className="p-2">
        <CardTitle className="px-2.5 pt-2">{t("admin.supplierDebts.cheques")}</CardTitle>
        <p className="px-2.5 text-[0.85rem] text-ink-2">{t("admin.supplierDebts.chequesHint")}</p>
        {data.cheques.length === 0 ? (
          <p className="px-2.5 py-3 text-ink-2">{t("admin.supplierDebts.noCheques")}</p>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.supplierDebts.columns.cashOn")}</Th>
                <Th>{t("admin.supplierDebts.columns.supplier")}</Th>
                <Th>{t("admin.supplierDebts.columns.method")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.supplierDebts.columns.payment")}</Th>
                <Th numeric>{t("admin.supplierDebts.columns.amount")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.cheques.map((cheque) => {
                const past = cheque.cash_on < today;
                return (
                  <tr key={cheque.payment_id} className={cn(past && "text-ink-2")}>
                    <Td className="num whitespace-nowrap">
                      {formatDate(cheque.cash_on)}
                      {cheque.cash_on === today && (
                        <Pill className="ms-2" tone="warn">
                          {t("admin.supplierDebts.today")}
                        </Pill>
                      )}
                      {past && (
                        <Pill className="ms-2" tone="neutral">
                          {t("admin.supplierDebts.past")}
                        </Pill>
                      )}
                    </Td>
                    <Td>
                      <Link to={`/fournisseurs/${cheque.supplier_id}`} className="font-semibold hover:underline">
                        {cheque.supplier_name}
                      </Link>
                    </Td>
                    <Td>
                      {t(`admin.supplierPayments.method.${cheque.method}`)}
                      {cheque.reference && <div className="num text-[0.8rem] text-ink-2">{cheque.reference}</div>}
                    </Td>
                    <Td className="num max-[720px]:hidden">
                      {cheque.number} · {formatDate(cheque.paid_on)}
                    </Td>
                    <Td numeric className="font-semibold whitespace-nowrap">
                      {formatMoney(cheque.amount)}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  );
}
