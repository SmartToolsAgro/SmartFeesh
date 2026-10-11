import {
  acceptQuote,
  ApiError,
  convertQuoteToSale,
  refuseQuote,
  sendQuote,
  useGetQuote,
  useListLocations,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatDateTime, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import {
  BRAND,
  BrandMark,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router";

import { fieldErrors } from "../lib/errors";
import { refreshAfterSale } from "../sales/shared";
import { canWriteQuotes, formatRate, refreshAfterQuote, STATUS_TONES } from "./shared";

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

/** One quote, laid out like the prototype's printed quote, with what happened to it and its actions. */
export function QuoteDetailPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reasonId = useId();
  const { quoteId } = useParams();
  const id = Number(quoteId);
  const validId = Number.isInteger(id) && id > 0;
  const quote = useGetQuote(id, { query: { enabled: validId, retry: false } });
  const [refusing, setRefusing] = useState(false);
  const [reason, setReason] = useState("");
  // P2-T04: an accepted quote becomes a sale, from the quote's place unless another is chosen.
  const convertId = useId();
  const [converting, setConverting] = useState(false);
  const [convertPlace, setConvertPlace] = useState("");
  const [convertError, setConvertError] = useState("");
  const locations = useListLocations({ status: "active" }, { query: { enabled: converting } });
  const convert = useMutation({
    mutationFn: (confirmNow: boolean) =>
      convertQuoteToSale(id, {
        location: convertPlace ? Number(convertPlace) : (quote.data?.location?.id ?? null),
        confirm_now: confirmNow,
      }),
    onSuccess: async (sale) => {
      toast.success(t("admin.sales.fromQuote.created", { number: sale.number }));
      setConverting(false);
      await refreshAfterSale(queryClient);
      void navigate(`/ventes/${sale.id}`);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setConvertError(Object.values(fromServer).join(" ") || t("admin.quotes.detail.actionError"));
    },
  });

  const onFailure = (failure: unknown) => {
    const fromServer = fieldErrors(failure);
    toast.error(Object.values(fromServer)[0] ?? t("admin.quotes.detail.actionError"));
  };
  const action = (
    run: () => Promise<{ number: string }>,
    done: "admin.quotes.detail.sent" | "admin.quotes.detail.accepted" | "admin.quotes.detail.refused",
  ) => ({
    mutationFn: run,
    onSuccess: async (saved: { number: string }) => {
      toast.success(t(done, { number: saved.number }));
      await refreshAfterQuote(queryClient);
    },
    onError: onFailure,
  });
  const send = useMutation(action(() => sendQuote(id), "admin.quotes.detail.sent"));
  const accept = useMutation(action(() => acceptQuote(id), "admin.quotes.detail.accepted"));
  const refuse = useMutation({
    ...action(() => refuseQuote(id, { reason: reason.trim() }), "admin.quotes.detail.refused"),
    onSettled: () => setRefusing(false),
  });

  const back = (
    <Link to="/devis" className="text-[0.85rem] font-semibold text-sea hover:underline">
      {t("admin.quotes.back")}
    </Link>
  );

  if (validId && quote.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!quote.data) {
    const missing = !validId || (quote.error instanceof ApiError && quote.error.status === 404);
    return (
      <>
        {back}
        <EmptyState illustration="mix" title={missing ? t("admin.quotes.notFound") : t("common.serverUnreachable")} />
      </>
    );
  }

  const data = quote.data;
  const none = t("admin.quotes.detail.none");
  const canWrite = canWriteQuotes(session);
  const busy = send.isPending || accept.isPending || refuse.isPending;
  const hasDiscount = !isZero(data.discount_total);
  const title = t("admin.quotes.detail.title", { number: data.number });
  const address = [data.customer.address, data.customer.city].filter(Boolean).join(", ");

  return (
    <>
      {back}
      <PageHeader eyebrow={t("admin.quotes.title")} title={data.number}>
        <Pill tone={STATUS_TONES[data.status]}>{t(`admin.quotes.statuses.${data.status}`)}</Pill>
        {canWrite && data.status === "draft" && (
          <>
            <Button onClick={() => void navigate(`/devis/${data.id}/modifier`)}>{t("admin.quotes.detail.edit")}</Button>
            <Button variant="primary" disabled={busy} onClick={() => send.mutate()}>
              <Icon name="check" />
              {send.isPending ? t("admin.quotes.detail.sending") : t("admin.quotes.detail.send")}
            </Button>
          </>
        )}
        {canWrite && data.status === "sent" && (
          <>
            <Button disabled={busy} onClick={() => setRefusing(true)}>
              {t("admin.quotes.detail.refuse")}
            </Button>
            <Button variant="primary" disabled={busy} onClick={() => accept.mutate()}>
              <Icon name="check" />
              {t("admin.quotes.detail.accept")}
            </Button>
          </>
        )}
        {canWrite && data.status === "accepted" && !data.sale && (
          <Button
            variant="primary"
            onClick={() => {
              setConvertPlace(data.location ? String(data.location.id) : "");
              setConvertError("");
              setConverting(true);
            }}
          >
            <Icon name="receipt" />
            {t("admin.sales.fromQuote.convert")}
          </Button>
        )}
      </PageHeader>

      <div className="grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] items-start gap-4 max-[1000px]:grid-cols-1">
        <article
          aria-label={title}
          className="relative overflow-hidden rounded-[6px] border border-line bg-surface p-7 shadow-card max-[600px]:p-4"
        >
          {data.status === "draft" && (
            <div
              aria-hidden="true"
              className="absolute top-[22px] -end-[38px] rotate-[35deg] bg-warn-soft px-11 py-1 text-[0.72rem] font-bold tracking-[0.1em] text-warn uppercase"
            >
              {t("admin.quotes.detail.stamp")}
            </div>
          )}
          <header className="mb-4 flex flex-wrap justify-between gap-4 border-b-2 border-ink pb-4">
            <div>
              <div className="flex items-center gap-2.5 font-display text-[1.1rem] font-extrabold">
                <BrandMark className="size-[30px]" />
                {BRAND.name}
              </div>
              <p className="mt-1.5 text-[0.82rem] text-ink-2">{t("admin.quotes.detail.tagline")}</p>
            </div>
            <div className="text-end">
              <h2>{title}</h2>
              <p className="num text-[0.85rem] text-ink-2">
                {t("admin.quotes.detail.dated", {
                  date: formatDate(data.quoted_on),
                  until: formatDate(data.valid_until),
                })}
              </p>
            </div>
          </header>
          <p className="mb-3">
            <span className="eyebrow">{t("admin.quotes.detail.customer")}</span>
            <br />
            <Link to={`/clients/${data.customer.id}`} className="font-bold text-ink hover:underline">
              {data.customer.name}
            </Link>
            {address && <span> · {address}</span>}
            {data.customer.tax_id && (
              <span className="num block text-[0.82rem] text-ink-2">
                {t("admin.quotes.detail.taxId", { taxId: data.customer.tax_id })}
              </span>
            )}
          </p>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.quotes.detail.product")}</Th>
                <Th numeric>{t("admin.quotes.detail.quantity")}</Th>
                <Th numeric>{t("admin.quotes.detail.price")}</Th>
                {hasDiscount && <Th numeric>{t("admin.quotes.detail.discount")}</Th>}
                <Th numeric>{t("admin.quotes.detail.amount")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={line.id}>
                  <Td>
                    {line.product.name}
                    <div className="num text-[0.8rem] text-ink-2">{line.product.reference}</div>
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
                </tr>
              ))}
            </tbody>
          </Table>
          <dl className="ms-auto mt-3.5 flex w-[min(320px,100%)] flex-col gap-1">
            {hasDiscount && (
              <>
                <TotalRow label={t("admin.quotes.detail.subtotal")}>{formatMoney(data.subtotal)}</TotalRow>
                <TotalRow label={t("admin.quotes.detail.discountTotal")}>−{formatMoney(data.discount_total)}</TotalRow>
              </>
            )}
            <TotalRow label={t("admin.quotes.detail.totalExclTax")}>{formatMoney(data.total_excl_tax)}</TotalRow>
            {/* VAT and the fiscal stamp come with invoicing (P2-T05). */}
            <div className="flex justify-between gap-4 text-ink-2">
              <dt>{t("admin.quotes.detail.tax")}</dt>
              <dd className="text-[0.85rem]">
                {data.tax_amount ? formatMoney(data.tax_amount) : t("admin.quotes.detail.taxLater")}
              </dd>
            </div>
            <TotalRow label={t("admin.quotes.detail.total")} grand>
              {formatMoney(data.total)}
            </TotalRow>
          </dl>
          {data.notes && (
            <p className="mt-4 border-t border-line pt-3 text-[0.9rem] whitespace-pre-line">{data.notes}</p>
          )}
        </article>

        <Card>
          <CardTitle>{t("admin.quotes.detail.followUp")}</CardTitle>
          <p role="note" className="mb-4 rounded-chip bg-surface-2 px-3 py-2 text-[0.9rem]">
            {t(`admin.quotes.detail.statusNotes.${data.status}`, { date: formatDate(data.valid_until) })}
          </p>
          <dl className="flex flex-col gap-3">
            <Detail label={t("admin.quotes.detail.createdBy")}>
              {data.created_by || none} · <span className="num">{formatDateTime(data.created_at)}</span>
            </Detail>
            {data.sent_at && (
              <Detail label={t("admin.quotes.detail.sentBy")}>
                {data.sent_by || none} · <span className="num">{formatDateTime(data.sent_at)}</span>
              </Detail>
            )}
            {data.answered_at && (
              <Detail
                label={t(
                  data.status === "refused" ? "admin.quotes.detail.refusedBy" : "admin.quotes.detail.acceptedBy",
                )}
              >
                {data.answered_by || none} · <span className="num">{formatDateTime(data.answered_at)}</span>
              </Detail>
            )}
            {data.refusal_reason && <Detail label={t("admin.quotes.detail.reason")}>{data.refusal_reason}</Detail>}
            {data.expired_at && (
              <Detail label={t("admin.quotes.detail.expiredAt")} numeric>
                {formatDateTime(data.expired_at)}
              </Detail>
            )}
            {data.location && <Detail label={t("admin.quotes.detail.location")}>{data.location.name}</Detail>}
            {data.sale && (
              <Detail label={t("admin.sales.fromQuote.sale")}>
                <Link to={`/ventes/${data.sale.id}`} className="font-semibold text-sea hover:underline">
                  {data.sale.number}
                </Link>{" "}
                · {t(`admin.sales.statuses.${data.sale.status}`)}
              </Detail>
            )}
          </dl>
        </Card>
      </div>

      <Dialog open={refusing} onOpenChange={setRefusing}>
        <DialogContent>
          <DialogTitle>{t("admin.quotes.detail.refuseTitle", { number: data.number })}</DialogTitle>
          <DialogDescription>{t("admin.quotes.detail.refuseBody")}</DialogDescription>
          <Field label={t("admin.quotes.detail.reasonLabel")} htmlFor={reasonId}>
            <Input id={reasonId} value={reason} maxLength={255} onChange={(event) => setReason(event.target.value)} />
          </Field>
          <DialogFooter>
            <Button onClick={() => setRefusing(false)}>{t("admin.quotes.detail.keep")}</Button>
            <Button variant="danger" disabled={refuse.isPending} onClick={() => refuse.mutate()}>
              {t("admin.quotes.detail.confirmRefuse")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={converting} onOpenChange={setConverting}>
        <DialogContent>
          <DialogTitle>{t("admin.sales.fromQuote.title", { number: data.number })}</DialogTitle>
          <DialogDescription>{t("admin.sales.fromQuote.body")}</DialogDescription>
          <Field label={t("admin.sales.fromQuote.location")} htmlFor={convertId} error={convertError}>
            <Select value={convertPlace} onValueChange={setConvertPlace}>
              <SelectTrigger id={convertId} aria-invalid={convertError ? true : undefined}>
                <SelectValue placeholder={t("admin.sales.form.choose")} />
              </SelectTrigger>
              <SelectContent>
                {(locations.data ?? [])
                  .filter((option) => option.sells)
                  .map((option) => (
                    <SelectItem key={option.id} value={String(option.id)}>
                      {option.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </Field>
          <DialogFooter>
            <Button onClick={() => setConverting(false)}>{t("admin.quotes.detail.keep")}</Button>
            <Button disabled={convert.isPending} onClick={() => convert.mutate(false)}>
              {t("admin.sales.fromQuote.draft")}
            </Button>
            <Button variant="primary" disabled={convert.isPending} onClick={() => convert.mutate(true)}>
              {t("admin.sales.fromQuote.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
