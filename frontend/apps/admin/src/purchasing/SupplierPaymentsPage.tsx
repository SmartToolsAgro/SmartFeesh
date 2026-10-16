import { type SupplierPayment, useGetSupplier, useListSupplierPayments } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatMoney, useTranslation } from "@frutti/i18n";
import { Button, Card, Dialog, EmptyState, Icon, Input, PageHeader, Pill, Table, Td, Th } from "@frutti/ui";
import { keepPreviousData } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link, useNavigate, useOutletContext, useSearchParams } from "react-router";

import { useDebounced } from "../lib/useDebounced";
import { canRecordReceipts } from "../receipts/shared";
import { AllocateDialog } from "./AllocateDialog";
import { compare } from "./allocation";
import { PurchasingTabs } from "./PurchasingTabs";
import { idFrom } from "./shared";

const PAGE_SIZE = 50;

export function SupplierPaymentsPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const canRecord = canRecordReceipts(session);
  const unallocatedId = useId();
  const [params, setParams] = useSearchParams();
  // `?fournisseur=3` (from the supplier page) shows one supplier's payments.
  const supplierId = idFrom(params.get("fournisseur"));
  const supplier = useGetSupplier(supplierId ?? 0, { query: { enabled: supplierId !== null } });
  const [search, setSearch] = useState("");
  const [onlyUnallocated, setOnlyUnallocated] = useState(false);
  const [offset, setOffset] = useState(0);
  const [allocating, setAllocating] = useState<SupplierPayment | null>(null);
  const query = useDebounced(search.trim());

  const payments = useListSupplierPayments(
    {
      limit: PAGE_SIZE,
      offset,
      unallocated: onlyUnallocated,
      ...(query ? { search: query } : {}),
      ...(supplierId ? { supplier: supplierId } : {}),
    },
    { query: { placeholderData: keepPreviousData } },
  );
  const page = payments.data;
  const list = page?.results ?? [];
  const filtering = query !== "" || onlyUnallocated || supplierId !== null;

  return (
    <>
      <PageHeader eyebrow={t("admin.nav.purchases")} title={t("admin.supplierPayments.title")}>
        {canRecord && (
          <Button
            variant="primary"
            onClick={() => void navigate(`/achats/paiements/nouveau${supplierId ? `?fournisseur=${supplierId}` : ""}`)}
          >
            <Icon name="plus" />
            {t("admin.supplierPayments.add")}
          </Button>
        )}
      </PageHeader>

      <PurchasingTabs />

      {!canRecord && <p className="text-ink-2">{t("admin.supplierInvoices.readOnly")}</p>}

      <Card className="filter-bar flex flex-wrap items-center gap-3 p-3">
        <Input
          type="search"
          aria-label={t("admin.supplierPayments.search")}
          placeholder={t("admin.supplierPayments.search")}
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setOffset(0);
          }}
          className="min-w-52 flex-[2_1_14rem]"
        />
        <label htmlFor={unallocatedId} className="flex items-center gap-2 text-[0.9rem]">
          <input
            id={unallocatedId}
            type="checkbox"
            checked={onlyUnallocated}
            onChange={(event) => {
              setOnlyUnallocated(event.target.checked);
              setOffset(0);
            }}
            className="size-4 accent-coral"
          />
          {t("admin.supplierPayments.onlyUnallocated")}
        </label>
        {supplierId !== null && (
          <span className="flex items-center gap-2 text-[0.9rem]">
            <Pill tone="sea">{t("admin.supplierInvoices.supplierFilter", { name: supplier.data?.name ?? "…" })}</Pill>
            <button
              type="button"
              className="font-semibold text-sea hover:underline"
              onClick={() => {
                setParams({});
                setOffset(0);
              }}
            >
              {t("admin.supplierInvoices.clearSupplier")}
            </button>
          </span>
        )}
        <span className="ms-auto text-[0.85rem] text-ink-2" aria-live="polite">
          {page && t("admin.supplierPayments.count", { count: page.count })}
        </span>
      </Card>

      {payments.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : payments.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : list.length === 0 ? (
        filtering ? (
          <p className="text-ink-2">{t("admin.supplierPayments.noMatch")}</p>
        ) : (
          <EmptyState illustration="fish" title={t("admin.supplierPayments.empty")}>
            {t("admin.supplierPayments.emptyBody")}
          </EmptyState>
        )
      ) : (
        <Card className="p-2">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.supplierPayments.columns.number")}</Th>
                <Th>{t("admin.supplierPayments.columns.date")}</Th>
                <Th>{t("admin.supplierPayments.columns.supplier")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.supplierPayments.columns.method")}</Th>
                <Th numeric>{t("admin.supplierPayments.columns.amount")}</Th>
                <Th className="max-[720px]:hidden">{t("admin.supplierPayments.columns.invoices")}</Th>
                <Th numeric>{t("admin.supplierPayments.columns.unallocated")}</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((payment) => {
                const hasAdvance = compare(payment.unallocated_amount, "0") > 0;
                return (
                  <tr key={payment.id}>
                    <Td className="num font-semibold whitespace-nowrap">{payment.number}</Td>
                    <Td className="num whitespace-nowrap">{formatDate(payment.paid_on)}</Td>
                    <Td>
                      <Link to={`/fournisseurs/${payment.supplier.id}`} className="font-semibold hover:underline">
                        {payment.supplier.name}
                      </Link>
                    </Td>
                    <Td className="max-[720px]:hidden">
                      {t(`admin.supplierPayments.method.${payment.method}`)}
                      {payment.reference && <div className="num text-[0.8rem] text-ink-2">{payment.reference}</div>}
                      {payment.cash_on && (
                        <div className="num text-[0.8rem] text-ink-2">
                          {t("admin.supplierDebts.cashOn", { date: formatDate(payment.cash_on) })}
                        </div>
                      )}
                    </Td>
                    <Td numeric className="font-semibold whitespace-nowrap">
                      {formatMoney(payment.amount)}
                    </Td>
                    <Td className="max-[720px]:hidden">
                      <ul className="flex flex-col gap-0.5">
                        {payment.allocations.map((allocation) => (
                          <li key={allocation.id} className="num text-[0.85rem] whitespace-nowrap">
                            <Link
                              to={`/achats/factures/${allocation.invoice.id}`}
                              className="font-semibold text-sea hover:underline"
                            >
                              {allocation.invoice.number}
                            </Link>{" "}
                            · {formatMoney(allocation.amount)}
                          </li>
                        ))}
                      </ul>
                    </Td>
                    <Td numeric className="whitespace-nowrap">
                      {hasAdvance ? (
                        <span className="flex flex-col items-end gap-1">
                          <span>
                            <Pill tone="warn" className="me-2">
                              {t("admin.supplierPayments.advance")}
                            </Pill>
                            {formatMoney(payment.unallocated_amount)}
                          </span>
                          {canRecord && (
                            <Button onClick={() => setAllocating(payment)}>
                              {t("admin.supplierPayments.allocate")}
                            </Button>
                          )}
                        </span>
                      ) : (
                        "—"
                      )}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
          {page && page.count > PAGE_SIZE && (
            <div className="flex items-center justify-end gap-2 p-2">
              <span className="me-auto text-[0.85rem] text-ink-2">
                {t("admin.supplierPayments.page", {
                  from: offset + 1,
                  to: Math.min(offset + PAGE_SIZE, page.count),
                  count: page.count,
                })}
              </span>
              <Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                {t("admin.supplierPayments.previous")}
              </Button>
              <Button disabled={!page.next} onClick={() => setOffset(offset + PAGE_SIZE)}>
                {t("admin.supplierPayments.next")}
              </Button>
            </div>
          )}
        </Card>
      )}

      <Dialog open={allocating !== null} onOpenChange={(open) => !open && setAllocating(null)}>
        {allocating && <AllocateDialog key={allocating.id} payment={allocating} onDone={() => setAllocating(null)} />}
      </Dialog>
    </>
  );
}
