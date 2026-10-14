import { ApiError, cancelSale, confirmSale, createInvoice, useGetSale } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDateTime, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  CardTitle,
  cn,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  EmptyState,
  Field,
  Icon,
  Input,
  PageHeader,
  Pill,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router";

import { DocumentFooter, DocumentHeader } from "../lib/DocumentFrame";
import { useSeller } from "../lib/documentSeller";
import { fieldErrors } from "../lib/errors";
import { formatRate } from "../quotes/shared";
import { PdfButton } from "../lib/PdfButton";
import { openPdf } from "../lib/pdf";
import { canSell, refreshAfterSale, STATUS_TONES } from "./shared";

const isZero = (value: string) => /^0+(\.0+)?$/.test(value);

function Detail({ label, children, numeric = false }: { label: string; children: ReactNode; numeric?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[0.78rem] font-semibold text-ink-2">{label}</dt>
      <dd className={cn("break-words", numeric && "num")}>{children}</dd>
    </div>
  );
}

function TotalRow({ label, children, grand = false }: { label: string; children: ReactNode; grand?: boolean }) {
  return (
    <div
      className={cn(
        "flex justify-between gap-4",
        grand && "mt-1 border-t-2 border-ink pt-1.5 text-[1.05rem] font-bold",
      )}
    >
      <dt>{label}</dt>
      <dd className="num">{children}</dd>
    </div>
  );
}

/** One sale: its lines and the lots they came from, what was paid and what is owed, and its actions. */
export function SaleDetailPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reasonId = useId();
  const { saleId } = useParams();
  const id = Number(saleId);
  const validId = Number.isInteger(id) && id > 0;
  const sale = useGetSale(id, { query: { enabled: validId, retry: false } });
  const seller = useSeller(session);
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");

  const onFailure = (failure: unknown) => {
    const fromServer = fieldErrors(failure);
    toast.error(Object.values(fromServer)[0] ?? t("admin.sales.detail.actionError"));
  };
  const confirm = useMutation({
    mutationFn: (approveCredit: boolean) => confirmSale(id, { approve_credit: approveCredit }),
    onSuccess: async (saved) => {
      if (saved.status === "draft") toast.warning(t("admin.payments.sale.pendingToast"));
      else toast.success(t("admin.sales.detail.confirmed", { number: saved.number }));
      await refreshAfterSale(queryClient);
    },
    onError: onFailure,
  });
  // "Valider et imprimer le BL": printing is what validates a draft (D-095); a sale held for credit approval
  // stays a draft and prints nothing.
  const validateAndPrint = useMutation({
    mutationFn: async () => {
      const saved = await confirmSale(id, { approve_credit: false });
      if (saved.status === "draft") toast.warning(t("admin.payments.sale.pendingToast"));
      else {
        toast.success(t("admin.sales.detail.confirmed", { number: saved.number }));
        await openPdf("delivery_note", id);
      }
      await refreshAfterSale(queryClient);
    },
    onError: onFailure,
  });
  const invoice = useMutation({
    mutationFn: () => createInvoice({ sale: id }),
    onSuccess: async (saved) => {
      toast.success(t("admin.sales.detail.invoiceReady"));
      await refreshAfterSale(queryClient);
      void navigate(`/factures/${saved.id}`);
    },
    onError: onFailure,
  });
  const cancel = useMutation({
    mutationFn: () => cancelSale(id, { reason: reason.trim() }),
    onSuccess: async (saved) => {
      toast.success(t("admin.sales.detail.cancelled", { number: saved.number }));
      setCancelling(false);
      await refreshAfterSale(queryClient);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      if (fromServer.reason) setReasonError(fromServer.reason);
      else onFailure(failure);
    },
  });

  const back = (
    <Link to="/ventes" className="text-[0.85rem] font-semibold text-sea hover:underline">
      {t("admin.sales.back")}
    </Link>
  );

  if (validId && sale.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!sale.data) {
    const missing = !validId || (sale.error instanceof ApiError && sale.error.status === 404);
    return (
      <>
        {back}
        <EmptyState illustration="mix" title={missing ? t("admin.sales.notFound") : t("common.serverUnreachable")} />
      </>
    );
  }

  const data = sale.data;
  const none = t("admin.sales.detail.none");
  const canWrite = canSell(session);
  const busy = confirm.isPending || cancel.isPending || invoice.isPending || validateAndPrint.isPending;
  const hasDiscount = !isZero(data.discount_total);
  const showCosts = data.cost_total !== null;

  return (
    <>
      {back}
      <PageHeader eyebrow={t("admin.sales.title")} title={data.number}>
        <Pill tone={STATUS_TONES[data.status]}>{t(`admin.sales.statuses.${data.status}`)}</Pill>
        {canWrite && data.status === "draft" && (
          <>
            <Button onClick={() => void navigate(`/ventes/${data.id}/modifier`)}>{t("admin.sales.detail.edit")}</Button>
            <Button variant="primary" disabled={busy} onClick={() => confirm.mutate(data.credit_status === "pending")}>
              <Icon name="check" />
              {confirm.isPending
                ? t("admin.sales.detail.confirming")
                : t(data.credit_status === "pending" ? "admin.payments.sale.approve" : "admin.sales.detail.confirm")}
            </Button>
            {data.credit_status !== "pending" && (
              <Button disabled={busy} onClick={() => validateAndPrint.mutate()}>
                <Icon name="receipt" />
                {t("admin.sales.detail.validateAndPrint")}
              </Button>
            )}
          </>
        )}
        {data.confirmed_at && (
          <PdfButton kind="delivery_note" id={data.id} label={t("admin.sales.detail.deliveryNote")} />
        )}
        {canWrite && data.status === "confirmed" && !data.invoice && (
          <Button variant="primary" disabled={busy} onClick={() => invoice.mutate()}>
            <Icon name="receipt" />
            {t("admin.sales.detail.invoice")}
          </Button>
        )}
        {canWrite && data.status !== "cancelled" && (
          <Button
            variant={data.status === "confirmed" ? "danger" : "secondary"}
            disabled={busy}
            onClick={() => {
              setReason("");
              setReasonError("");
              setCancelling(true);
            }}
          >
            {t("admin.sales.detail.cancel")}
          </Button>
        )}
      </PageHeader>

      {data.credit_status === "pending" && (
        <p role="alert" className="rounded-chip bg-warn-soft px-3 py-2 text-[0.9rem]">
          {t("admin.payments.sale.pending", { amount: formatMoney(data.credit_over_by) })}
        </p>
      )}
      {(data.credit_status === "approved" || data.credit_status === "warned") && (
        <p role="note" className="rounded-chip bg-surface-2 px-3 py-2 text-[0.9rem]">
          {t(`admin.payments.sale.${data.credit_status}`, {
            amount: formatMoney(data.credit_over_by),
            name: data.credit_decided_by,
          })}
        </p>
      )}

      <div className="grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] items-start gap-4 max-[1000px]:grid-cols-1">
        <Card aria-label={t("admin.sales.detail.title", { number: data.number })} role="region">
          <DocumentHeader
            seller={seller}
            logoUrl={session.organization.logo_url}
            title={t("admin.documents.frame.deliveryNote")}
            number={data.number}
            date={data.sold_at}
            party={data.customer}
          />
          <CardTitle>{t("admin.sales.detail.lines")}</CardTitle>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.sales.detail.product")}</Th>
                <Th numeric>{t("admin.sales.detail.quantity")}</Th>
                <Th numeric>{t("admin.sales.detail.price")}</Th>
                {hasDiscount && <Th numeric>{t("admin.sales.detail.discount")}</Th>}
                <Th numeric>{t("admin.sales.detail.amount")}</Th>
                {showCosts && <Th numeric>{t("admin.sales.detail.cost")}</Th>}
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={line.id}>
                  <Td>
                    {line.product.name}
                    <div className="num text-[0.8rem] text-ink-2">
                      {line.product.reference} · {t(`admin.sales.priceSources.${line.price_source}`)}
                    </div>
                    {line.below_minimum && (
                      <Pill tone="warn" className="mt-1">
                        {t("admin.sales.detail.belowMinimum")}
                      </Pill>
                    )}
                    {line.batches && line.batches.length > 0 && (
                      <ul aria-label={t("admin.sales.detail.lots")} className="mt-1 text-[0.8rem] text-ink-2">
                        {line.batches.map((row) => (
                          <li key={row.id}>
                            <Link to={`/stock/lots/${row.batch.id}`} className="text-sea hover:underline">
                              {t("admin.sales.detail.lot", {
                                number: row.batch.number,
                                quantity: formatQuantity(row.quantity),
                                cost: formatMoney(row.unit_cost),
                              })}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatQuantity(line.quantity)}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatMoney(line.unit_price)}
                  </Td>
                  {hasDiscount && (
                    <Td numeric className="whitespace-nowrap">
                      {isZero(line.discount_rate) ? none : formatRate(line.discount_rate)}
                    </Td>
                  )}
                  <Td numeric className="font-semibold whitespace-nowrap">
                    {formatMoney(line.amount)}
                  </Td>
                  {showCosts && (
                    <Td numeric className="whitespace-nowrap text-ink-2">
                      {line.cost_amount ? formatMoney(line.cost_amount) : none}
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
          <dl className="ms-auto mt-3.5 flex w-[min(340px,100%)] flex-col gap-1">
            {hasDiscount && (
              <>
                <TotalRow label={t("admin.sales.detail.subtotal")}>{formatMoney(data.subtotal)}</TotalRow>
                <TotalRow label={t("admin.sales.detail.discountTotal")}>−{formatMoney(data.discount_total)}</TotalRow>
              </>
            )}
            <TotalRow label={t("admin.sales.detail.totalExclTax")}>{formatMoney(data.total_excl_tax)}</TotalRow>
            {/* VAT and the fiscal stamp come with invoicing (P2-T05). */}
            <div className="flex justify-between gap-4 text-ink-2">
              <dt>{t("admin.sales.detail.tax")}</dt>
              <dd className="text-[0.85rem]">
                {data.tax_amount ? formatMoney(data.tax_amount) : t("admin.sales.detail.taxLater")}
              </dd>
            </div>
            <TotalRow label={t("admin.sales.detail.total")} grand>
              {formatMoney(data.total)}
            </TotalRow>
            <TotalRow label={t("admin.sales.detail.paid")}>{formatMoney(data.amount_paid)}</TotalRow>
            <TotalRow label={t("admin.sales.detail.due")}>{formatMoney(data.amount_due)}</TotalRow>
            {data.cost_total !== null && data.margin !== null && (
              <>
                <TotalRow label={t("admin.sales.detail.costTotal")}>{formatMoney(data.cost_total)}</TotalRow>
                <TotalRow label={t("admin.sales.detail.margin")}>{formatMoney(data.margin)}</TotalRow>
              </>
            )}
          </dl>
          {data.notes && (
            <p className="mt-4 border-t border-line pt-3 text-[0.9rem] whitespace-pre-line">{data.notes}</p>
          )}
          <DocumentFooter seller={seller} />
        </Card>

        <Card>
          <CardTitle>{t("admin.sales.detail.followUp")}</CardTitle>
          <p role="note" className="mb-4 rounded-chip bg-surface-2 px-3 py-2 text-[0.9rem]">
            {t(`admin.sales.detail.statusNotes.${data.status}`)}
          </p>
          <dl className="flex flex-col gap-3">
            <Detail label={t("admin.sales.detail.customer")}>
              <Link to={`/clients/${data.customer.id}`} className="font-semibold text-ink hover:underline">
                {data.customer.name}
              </Link>
            </Detail>
            <Detail label={t("admin.sales.detail.soldAt")} numeric>
              {formatDateTime(data.sold_at)}
            </Detail>
            {data.invoice && (
              <Detail label={t("admin.sales.detail.invoiceLabel")}>
                <Link to={`/factures/${data.invoice.id}`} className="font-semibold text-sea hover:underline">
                  {data.invoice.number || t("admin.invoices.draftNumber")}
                </Link>
              </Detail>
            )}
            {data.quote && (
              <Detail label={t("admin.sales.detail.quote")}>
                <Link to={`/devis/${data.quote.id}`} className="font-semibold text-sea hover:underline">
                  {data.quote.number}
                </Link>
              </Detail>
            )}
            <Detail label={t("admin.sales.detail.payment")}>
              {data.payment_method
                ? t("admin.sales.detail.paymentLine", {
                    method: t(`admin.sales.methods.${data.payment_method}`),
                    amount: formatMoney(data.amount_paid),
                  })
                : t("admin.sales.detail.nothingPaid")}
              {data.payment_reference && <span className="num block text-ink-2">{data.payment_reference}</span>}
            </Detail>
            <Detail label={t("admin.sales.detail.createdBy")}>
              {data.created_by || none} · <span className="num">{formatDateTime(data.created_at)}</span>
            </Detail>
            {data.confirmed_at && (
              <Detail label={t("admin.sales.detail.confirmedBy")}>
                {data.confirmed_by || none} · <span className="num">{formatDateTime(data.confirmed_at)}</span>
              </Detail>
            )}
            {data.cancelled_at && (
              <Detail label={t("admin.sales.detail.cancelledBy")}>
                {data.cancelled_by || none} · <span className="num">{formatDateTime(data.cancelled_at)}</span>
              </Detail>
            )}
            {data.cancel_reason && <Detail label={t("admin.sales.detail.cancelReason")}>{data.cancel_reason}</Detail>}
          </dl>
        </Card>
      </div>

      <Dialog open={cancelling} onOpenChange={setCancelling}>
        <DialogContent>
          <DialogTitle>{t("admin.sales.detail.cancelTitle", { number: data.number })}</DialogTitle>
          <DialogDescription>
            {data.status === "confirmed"
              ? t("admin.sales.detail.cancelConfirmedBody")
              : t("admin.sales.detail.cancelDraftBody")}
          </DialogDescription>
          <Field label={t("admin.sales.detail.reasonLabel")} htmlFor={reasonId} error={reasonError}>
            <Input
              id={reasonId}
              value={reason}
              maxLength={255}
              onChange={(event) => setReason(event.target.value)}
              aria-invalid={reasonError ? true : undefined}
            />
          </Field>
          <DialogFooter>
            <Button onClick={() => setCancelling(false)}>{t("admin.sales.detail.keep")}</Button>
            <Button variant="danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {t("admin.sales.detail.confirmCancel")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
