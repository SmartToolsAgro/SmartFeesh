import { type SaleStatusEnum, useListSales } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDateTime, formatMoney, useTranslation } from "@frutti/i18n";
import { Button, Card, cn, EmptyState, Icon, Input, PageHeader, Pill, Table, Td, Th } from "@frutti/ui";
import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router";

import { useDebounced } from "../lib/useDebounced";
import { canSell, SALE_STATUSES, STATUS_TONES } from "./shared";

const PAGE_SIZE = 50;
const isZero = (value: string) => /^0+(\.0+)?$/.test(value);

/** "Ventes": every sale, newest first, with what the customer still owes on it. */
export function SalesPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const canWrite = canSell(session);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<SaleStatusEnum | "">("");
  const [offset, setOffset] = useState(0);
  const query = useDebounced(search.trim());

  const sales = useListSales(
    { limit: PAGE_SIZE, offset, ...(status ? { status } : {}), ...(query ? { search: query } : {}) },
    { query: { placeholderData: keepPreviousData } },
  );
  const page = sales.data;
  const list = page?.results ?? [];
  const filtering = query !== "" || status !== "";

  const statusButton = (value: SaleStatusEnum | "", label: string) => (
    <button
      key={value || "all"}
      type="button"
      aria-pressed={status === value}
      onClick={() => {
        setStatus(value);
        setOffset(0);
      }}
      className={cn(
        "rounded-[7px] px-3 py-1.5 text-[0.85rem] font-semibold text-ink-2",
        status === value && "bg-surface text-ink shadow-card",
      )}
    >
      {label}
    </button>
  );

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.sales")} title={t("admin.sales.title")}>
        {canWrite && (
          <>
            <Button onClick={() => void navigate("/ventes/nouvelle")}>
              <Icon name="plus" />
              {t("admin.sales.add")}
            </Button>
            <Button variant="primary" onClick={() => void navigate("/ventes/comptoir")}>
              <Icon name="cash" />
              {t("admin.sales.counter")}
            </Button>
          </>
        )}
      </PageHeader>

      {!canWrite && <p className="text-ink-2">{t("admin.sales.readOnly")}</p>}

      <Card className="flex flex-wrap items-center gap-3 p-3">
        <Input
          type="search"
          aria-label={t("admin.sales.search")}
          placeholder={t("admin.sales.search")}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setOffset(0);
          }}
          className="min-w-52 flex-[2_1_14rem]"
        />
        <div
          role="group"
          aria-label={t("admin.sales.statusFilter")}
          className="flex flex-wrap rounded-control bg-surface-2 p-1"
        >
          {statusButton("", t("admin.sales.allStatuses"))}
          {SALE_STATUSES.map((value) => statusButton(value, t(`admin.sales.statuses.${value}`)))}
        </div>
        <span className="ms-auto text-[0.85rem] text-ink-2" aria-live="polite">
          {page && t("admin.sales.count", { count: page.count })}
        </span>
      </Card>

      {sales.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : sales.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : list.length === 0 ? (
        filtering ? (
          <p className="text-ink-2">{t("admin.sales.noMatch")}</p>
        ) : (
          <EmptyState illustration="truck" title={t("admin.sales.empty")}>
            {t("admin.sales.emptyBody")}
          </EmptyState>
        )
      ) : (
        <Card className="p-2">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.sales.columns.number")}</Th>
                <Th>{t("admin.sales.columns.date")}</Th>
                <Th>{t("admin.sales.columns.customer")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.sales.columns.location")}</Th>
                <Th numeric>{t("admin.sales.columns.total")}</Th>
                <Th numeric className="max-[720px]:hidden">
                  {t("admin.sales.columns.due")}
                </Th>
              </tr>
            </thead>
            <tbody>
              {list.map((sale) => (
                // The number is the link; a click anywhere on the row opens the same page.
                <tr
                  key={sale.id}
                  onClick={() => void navigate(`/ventes/${sale.id}`)}
                  className="cursor-pointer hover:bg-surface-2"
                >
                  <Td className="num whitespace-nowrap">
                    <Link
                      to={`/ventes/${sale.id}`}
                      className="font-semibold text-ink hover:underline"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {sale.number}
                    </Link>
                    <Pill className="ms-2" tone={STATUS_TONES[sale.status]}>
                      {t(`admin.sales.statuses.${sale.status}`)}
                    </Pill>
                  </Td>
                  <Td className="num whitespace-nowrap">{formatDateTime(sale.sold_at)}</Td>
                  <Td>
                    <span className="font-semibold">{sale.customer.name}</span>
                    <div className="num text-[0.8rem] text-ink-2">{sale.customer.reference}</div>
                  </Td>
                  <Td className="max-[720px]:hidden">{sale.location.name}</Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatMoney(sale.total_excl_tax)}
                  </Td>
                  <Td
                    numeric
                    className={cn(
                      "whitespace-nowrap max-[720px]:hidden",
                      sale.status === "confirmed" && !isZero(sale.amount_due) && "font-semibold text-warn",
                    )}
                  >
                    {sale.status === "confirmed" ? formatMoney(sale.amount_due) : "—"}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          {page && page.count > PAGE_SIZE && (
            <div className="flex items-center justify-end gap-2 p-2">
              <span className="me-auto text-[0.85rem] text-ink-2">
                {t("admin.sales.page", {
                  from: offset + 1,
                  to: Math.min(offset + PAGE_SIZE, page.count),
                  count: page.count,
                })}
              </span>
              <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                {t("admin.sales.previous")}
              </Button>
              <Button disabled={!page.next} onClick={() => setOffset(offset + PAGE_SIZE)}>
                {t("admin.sales.next")}
              </Button>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
