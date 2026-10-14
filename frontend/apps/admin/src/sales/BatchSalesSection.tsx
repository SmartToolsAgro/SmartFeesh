import { useGetBatchSales } from "@frutti/api";
import { formatDateTime, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Card, Table, Td, Th } from "@frutti/ui";
import { type ReactNode } from "react";
import { Link } from "react-router";

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[0.78rem] font-semibold text-ink-2">{label}</dt>
      <dd className="num text-[1.1rem] font-semibold">{children}</dd>
    </div>
  );
}

/** What one lot sold over its confirmed sales (D-040, D-051): kg, revenue, cost, margin, and each sale. */
export function BatchSalesSection({ batchId }: { batchId: number }) {
  const { t } = useTranslation();
  const sales = useGetBatchSales(batchId, { query: { enabled: Number.isInteger(batchId) && batchId > 0 } });
  const data = sales.data;

  return (
    <section aria-labelledby="batch-sales" className="flex flex-col gap-2">
      <h2 id="batch-sales">{t("admin.sales.batch.title")}</h2>
      {data && (
        <Card className="flex flex-col gap-4 p-4">
          <dl className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(10rem,1fr))]">
            <Figure label={t("admin.sales.batch.sold")}>{formatQuantity(data.quantity)}</Figure>
            <Figure label={t("admin.sales.batch.revenue")}>{formatMoney(data.revenue)}</Figure>
            <Figure label={t("admin.sales.batch.cost")}>{formatMoney(data.cost)}</Figure>
            <Figure label={t("admin.sales.batch.margin")}>{formatMoney(data.margin)}</Figure>
          </dl>
          {data.rows.length === 0 ? (
            <p className="text-ink-2">{t("admin.sales.batch.none")}</p>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.sales.batch.sale")}</Th>
                  <Th>{t("admin.sales.batch.date")}</Th>
                  <Th>{t("admin.sales.batch.customer")}</Th>
                  <Th numeric>{t("admin.sales.batch.quantity")}</Th>
                  <Th numeric className="max-[720px]:hidden">
                    {t("admin.sales.batch.price")}
                  </Th>
                  <Th numeric>{t("admin.sales.batch.amount")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.id}>
                    <Td className="num whitespace-nowrap">
                      <Link to={`/ventes/${row.sale.id}`} className="font-semibold text-sea hover:underline">
                        {row.sale.number}
                      </Link>
                    </Td>
                    <Td className="num whitespace-nowrap">{formatDateTime(row.sold_at)}</Td>
                    <Td>{row.customer}</Td>
                    <Td numeric className="whitespace-nowrap">
                      {formatQuantity(row.quantity)}
                    </Td>
                    <Td numeric className="whitespace-nowrap max-[720px]:hidden">
                      {formatMoney(row.unit_price)}
                    </Td>
                    <Td numeric className="font-semibold whitespace-nowrap">
                      {formatMoney(row.revenue_amount)}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}
    </section>
  );
}
