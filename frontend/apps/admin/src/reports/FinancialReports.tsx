import {
  useGetCashFlowReport,
  useGetCustomerBalancesReport,
  useGetMonthResultReport,
  useGetSupplierBalancesReport,
  useGetUnpaidSalariesReport,
} from "@frutti/api";
import { formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Button, Card, cn, EmptyState, Field, Input, Table, Td, Th } from "@frutti/ui";
import { useId, useState } from "react";

const VIEWS = ["result", "cash", "customers", "suppliers", "salaries"] as const;
type View = (typeof VIEWS)[number];
const CASH_GROUPS = ["day", "week", "month"] as const;

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => `${today().slice(0, 8)}01`;

function ExportLink({ path, query }: { path: string; query: Record<string, string | number> }) {
  const { t } = useTranslation();
  const search = new URLSearchParams(Object.entries(query).map(([key, value]) => [key, String(value)]));
  return (
    <Button asChild>
      <a href={`/api/v1/reports/${path}/export?${search.toString()}`} download>
        {t("admin.reports.excel")}
      </a>
    </Button>
  );
}

function Status({ query }: { query: { isPending: boolean; isError: boolean } }) {
  const { t } = useTranslation();
  if (query.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (query.isError) {
    return (
      <p role="alert" className="text-bad">
        {t("common.serverUnreachable")}
      </p>
    );
  }
  return null;
}

function Empty() {
  const { t } = useTranslation();
  return (
    <EmptyState illustration="mussel" title={t("admin.reports.empty")}>
      {t("admin.reports.emptyBody")}
    </EmptyState>
  );
}

function Line({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <p className={cn("flex justify-between gap-3", strong && "text-[1.05rem] font-bold")}>
      <span className={strong ? "" : "text-ink-2"}>{label}</span>
      <span className="num">{value}</span>
    </p>
  );
}

function MonthResult() {
  const { t } = useTranslation();
  const monthId = useId();
  const [month, setMonth] = useState(today().slice(0, 7));
  const query = { month: `${month}-01` };
  const report = useGetMonthResultReport(query);
  const data = report.data;
  return (
    <>
      <Card className="filter-bar flex flex-wrap items-end gap-3 p-3">
        <Field label={t("admin.reports.month")} htmlFor={monthId}>
          <Input id={monthId} type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
        </Field>
        <ExportLink path="month-result" query={query} />
      </Card>
      <Status query={report} />
      {data && (
        <Card className="max-w-xl space-y-2">
          <Line label={t("admin.reports.revenue")} value={formatMoney(data.revenue)} />
          <Line label={t("admin.reports.cogs")} value={formatMoney(data.cogs)} />
          <Line label={t("admin.reports.margin")} value={formatMoney(data.gross_margin)} strong />
          <Line label={t("admin.reports.spoilage")} value={formatMoney(data.spoilage)} />
          <Line label={t("admin.reports.expenses")} value={formatMoney(data.expenses_total)} />
          <Line label={t("admin.reports.personnel")} value={formatMoney(data.personnel)} />
          <Line label={t("admin.reports.netResult")} value={formatMoney(data.net_result)} strong />
          <p className="text-[0.85rem] text-ink-2">
            {t("admin.reports.salesCount", { count: data.sales_count, kg: formatQuantity(data.quantity_sold) })}
          </p>
        </Card>
      )}
      {data && data.categories.length > 0 && (
        <Card className="p-2">
          <h2 className="px-3 pt-2">{t("admin.reports.expensesByCategory")}</h2>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.reports.category")}</Th>
                <Th className="text-end">{t("admin.reports.count")}</Th>
                <Th className="text-end">{t("admin.reports.amount")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.categories.map((category) => (
                <tr key={category.name}>
                  <Td>{category.name}</Td>
                  <Td className="num text-end">{category.count}</Td>
                  <Td className="num text-end">{formatMoney(category.total)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </>
  );
}

function CashFlow() {
  const { t } = useTranslation();
  const fromId = useId();
  const toId = useId();
  const [group, setGroup] = useState<(typeof CASH_GROUPS)[number]>("day");
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const query = { group_by: group, date_from: from, date_to: to };
  const report = useGetCashFlowReport(query);
  const data = report.data;
  return (
    <>
      <Card className="filter-bar flex flex-wrap items-end gap-3 p-3">
        <div role="group" aria-label={t("admin.reports.groupBy")} className="flex rounded-control bg-surface-2 p-1">
          {CASH_GROUPS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={group === value}
              onClick={() => setGroup(value)}
              className={cn(
                "rounded-[7px] px-3 py-1.5 text-[0.85rem] font-semibold text-ink-2",
                group === value && "bg-surface text-ink shadow-card",
              )}
            >
              {t(`admin.reports.groups.${value}`)}
            </button>
          ))}
        </div>
        <Field label={t("admin.reports.from")} htmlFor={fromId}>
          <Input id={fromId} type="date" value={from} max={to} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label={t("admin.reports.to")} htmlFor={toId}>
          <Input id={toId} type="date" value={to} min={from} onChange={(event) => setTo(event.target.value)} />
        </Field>
        <ExportLink path="cash-flow" query={query} />
      </Card>
      <Status query={report} />
      {data &&
        (data.rows.length === 0 ? (
          <Empty />
        ) : (
          <Card className="p-2">
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.reports.period")}</Th>
                  <Th className="text-end">{t("admin.reports.cashIn")}</Th>
                  <Th className="text-end">{t("admin.reports.cashOut")}</Th>
                  <Th className="text-end">{t("admin.reports.balance")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.key}>
                    <Td>{row.key}</Td>
                    <Td className="num text-end">{formatMoney(row.cash_in)}</Td>
                    <Td className="num text-end">{formatMoney(row.cash_out)}</Td>
                    <Td className="num text-end">{formatMoney(row.net)}</Td>
                  </tr>
                ))}
                <tr className="font-bold">
                  <Td>{t("admin.reports.total")}</Td>
                  <Td className="num text-end">{formatMoney(data.total_in)}</Td>
                  <Td className="num text-end">{formatMoney(data.total_out)}</Td>
                  <Td className="num text-end">{formatMoney(data.net)}</Td>
                </tr>
              </tbody>
            </Table>
          </Card>
        ))}
      <p className="text-[0.85rem] text-ink-2">{t("admin.reports.cashNote")}</p>
    </>
  );
}

function Customers() {
  const { t } = useTranslation();
  const report = useGetCustomerBalancesReport();
  const data = report.data;
  return (
    <>
      <Card className="filter-bar flex items-center justify-end p-3">
        <ExportLink path="customer-balances" query={{}} />
      </Card>
      <Status query={report} />
      {data &&
        (data.rows.length === 0 ? (
          <Empty />
        ) : (
          <Card className="p-2">
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.reports.groups.customer")}</Th>
                  <Th className="text-end">{t("admin.reports.owed")}</Th>
                  <Th className="text-end">{t("admin.reports.overdue")}</Th>
                  <Th className="text-end">0-30 j</Th>
                  <Th className="text-end">31-60 j</Th>
                  <Th className="text-end">61+ j</Th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.customer_id}>
                    <Td>{row.name}</Td>
                    <Td className="num text-end">{formatMoney(row.balance)}</Td>
                    <Td className="num text-end">{formatMoney(row.overdue)}</Td>
                    <Td className="num text-end">{formatMoney(row.d0_30)}</Td>
                    <Td className="num text-end">{formatMoney(row.d31_60)}</Td>
                    <Td className="num text-end">{formatMoney(row.d60_plus)}</Td>
                  </tr>
                ))}
                <tr className="font-bold">
                  <Td>{t("admin.reports.total")}</Td>
                  <Td className="num text-end">{formatMoney(data.total_balance)}</Td>
                  <Td className="num text-end">{formatMoney(data.total_overdue)}</Td>
                  <Td className="num text-end">{formatMoney(data.d0_30)}</Td>
                  <Td className="num text-end">{formatMoney(data.d31_60)}</Td>
                  <Td className="num text-end">{formatMoney(data.d60_plus)}</Td>
                </tr>
              </tbody>
            </Table>
          </Card>
        ))}
    </>
  );
}

function Suppliers() {
  const { t } = useTranslation();
  const report = useGetSupplierBalancesReport();
  const data = report.data;
  return (
    <>
      <Card className="filter-bar flex items-center justify-between gap-3 p-3">
        <span className="text-ink-2">{t("admin.reports.suppliersNote")}</span>
        <ExportLink path="supplier-balances" query={{}} />
      </Card>
      <Status query={report} />
      {data &&
        (data.rows.length === 0 ? (
          <Empty />
        ) : (
          <Card className="p-2">
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.reports.supplier")}</Th>
                  <Th className="text-end">{t("admin.reports.invoiced")}</Th>
                  <Th className="text-end">{t("admin.reports.paid")}</Th>
                  <Th className="text-end">{t("admin.reports.owed")}</Th>
                  <Th className="text-end">{t("admin.reports.overdue")}</Th>
                  <Th className="text-end">{t("admin.reports.uninvoiced")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.supplier_id}>
                    <Td>{row.name}</Td>
                    <Td className="num text-end">{formatMoney(row.invoiced)}</Td>
                    <Td className="num text-end">{formatMoney(row.paid)}</Td>
                    <Td className="num text-end">{formatMoney(row.balance)}</Td>
                    <Td className="num text-end">{formatMoney(row.overdue)}</Td>
                    <Td className="num text-end">{formatMoney(row.uninvoiced)}</Td>
                  </tr>
                ))}
                <tr className="font-bold">
                  <Td>{t("admin.reports.total")}</Td>
                  <Td />
                  <Td />
                  <Td className="num text-end">{formatMoney(data.total_balance)}</Td>
                  <Td className="num text-end">{formatMoney(data.total_overdue)}</Td>
                  <Td className="num text-end">{formatMoney(data.total_uninvoiced)}</Td>
                </tr>
              </tbody>
            </Table>
          </Card>
        ))}
    </>
  );
}

function Salaries() {
  const { t } = useTranslation();
  const report = useGetUnpaidSalariesReport();
  const data = report.data;
  return (
    <>
      <Card className="filter-bar flex items-center justify-end p-3">
        <ExportLink path="unpaid-salaries" query={{}} />
      </Card>
      <Status query={report} />
      {data &&
        (data.rows.length === 0 ? (
          <Empty />
        ) : (
          <Card className="p-2">
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.reports.employee")}</Th>
                  <Th className="text-end">{t("admin.reports.toPay")}</Th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.employee_id}>
                    <Td>{row.name}</Td>
                    <Td className="num text-end">{formatMoney(row.unpaid)}</Td>
                  </tr>
                ))}
                <tr className="font-bold">
                  <Td>{t("admin.reports.total")}</Td>
                  <Td className="num text-end">{formatMoney(data.total)}</Td>
                </tr>
              </tbody>
            </Table>
          </Card>
        ))}
    </>
  );
}

/** The "Finances" tab: the owner's and the accountant's money reports (P7-T04, D-116). */
export function FinancialReports() {
  const { t } = useTranslation();
  const [view, setView] = useState<View>("result");
  return (
    <>
      <div role="group" aria-label={t("admin.reports.tabs.financial")} className="flex flex-wrap gap-1 self-start">
        {VIEWS.map((value) => (
          <Button
            key={value}
            variant={view === value ? "primary" : "secondary"}
            aria-pressed={view === value}
            onClick={() => setView(value)}
          >
            {t(`admin.reports.financial.${value}`)}
          </Button>
        ))}
      </div>
      {view === "result" && <MonthResult />}
      {view === "cash" && <CashFlow />}
      {view === "customers" && <Customers />}
      {view === "suppliers" && <Suppliers />}
      {view === "salaries" && <Salaries />}
    </>
  );
}
