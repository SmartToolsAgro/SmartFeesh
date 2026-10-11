import {
  ApiError,
  cancelTransfer,
  type TransferDetail,
  useGetTransfer,
  useGetTruckDay,
  validateTransfer,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatDateTime, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
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
  Icon,
  PageHeader,
  Pill,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useOutletContext, useParams } from "react-router";

import { fieldErrors } from "../lib/errors";
import { canRecordTransfers, isZero, KIND_ICONS, refreshAfterTransfer, STATUS_TONES } from "./shared";

function Detail({ label, children, numeric = false }: { label: string; children: ReactNode; numeric?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[0.78rem] font-semibold text-ink-2">{label}</dt>
      <dd className={cn("break-words", numeric && "num")}>{children}</dd>
    </div>
  );
}

/** The truck a transfer loads or unloads, if any: its day is shown below the transfer. */
function truckOf(transfer: TransferDetail) {
  if (transfer.to_location.kind === "truck") return transfer.to_location;
  if (transfer.from_location.kind === "truck") return transfer.from_location;
  return null;
}

/** Loaded − returned = sold or lost, per product, for the truck's day (client meeting 2026-10-11). */
function TruckDayCard({ locationId, day }: { locationId: number; day: string }) {
  const { t } = useTranslation();
  const truckDay = useGetTruckDay({ location: locationId, date: day });
  if (!truckDay.data) return null;
  const data = truckDay.data;
  const none = t("admin.transfers.detail.none");
  return (
    <Card
      className="p-2"
      role="region"
      aria-label={t("admin.transfers.day.title", { location: data.location.name, date: formatDate(data.date) })}
    >
      <CardTitle className="px-2.5 pt-2">
        {t("admin.transfers.day.title", { location: data.location.name, date: formatDate(data.date) })}
      </CardTitle>
      <p className="px-2.5 pb-2 text-[0.85rem] text-ink-2">{t("admin.transfers.day.intro")}</p>
      {data.lines.length === 0 ? (
        <p className="px-2.5 pb-2 text-ink-2">{t("admin.transfers.day.empty")}</p>
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.transfers.day.product")}</Th>
                <Th numeric>{t("admin.transfers.day.loaded")}</Th>
                <Th numeric>{t("admin.transfers.day.returned")}</Th>
                <Th numeric>{t("admin.transfers.day.soldOrLost")}</Th>
                <Th numeric className="max-[720px]:hidden">
                  {t("admin.transfers.day.price")}
                </Th>
                <Th numeric>{t("admin.transfers.day.amount")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line) => (
                <tr key={line.product_id}>
                  <Td>
                    <span className="font-semibold">{line.product_name}</span>
                    <div className="num text-[0.8rem] text-ink-2">{line.product_reference}</div>
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatQuantity(line.loaded)}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatQuantity(line.returned)}
                  </Td>
                  <Td
                    numeric
                    className={cn("font-semibold whitespace-nowrap", !isZero(line.sold_or_lost) && "text-coral")}
                  >
                    {formatQuantity(line.sold_or_lost)}
                  </Td>
                  <Td numeric className="whitespace-nowrap max-[720px]:hidden">
                    {line.unit_price ? formatMoney(line.unit_price) : none}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {line.amount ? formatMoney(line.amount) : none}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <dl className="flex justify-end border-t border-line px-2.5 py-3">
            <Detail label={t("admin.transfers.day.total")} numeric>
              <b>{formatMoney(data.amount)}</b>
            </Detail>
          </dl>
        </>
      )}
    </Card>
  );
}

export function TransferDetailPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { transferId } = useParams();
  const id = Number(transferId);
  const validId = Number.isInteger(id) && id > 0;
  const transfer = useGetTransfer(id, { query: { enabled: validId, retry: false } });
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [lineErrors, setLineErrors] = useState<Record<string, string>>({});

  const onFailure = (failure: unknown) => {
    const fromServer = fieldErrors(failure);
    setLineErrors(fromServer);
    const message =
      fromServer.detail ?? fromServer.transferred_on ?? fromServer.from_location ?? fromServer.to_location;
    if (message || Object.keys(fromServer).length === 0)
      toast.error(message ?? t("admin.transfers.detail.actionError"));
  };
  const validate = useMutation({
    mutationFn: () => validateTransfer(id),
    onSuccess: async (saved) => {
      setLineErrors({});
      toast.success(t("admin.transfers.detail.validated", { number: saved.number }));
      await refreshAfterTransfer(queryClient);
    },
    onError: onFailure,
  });
  const cancel = useMutation({
    mutationFn: () => cancelTransfer(id),
    onSuccess: async (saved) => {
      setConfirmCancel(false);
      toast.success(t("admin.transfers.detail.cancelled", { number: saved.number }));
      await refreshAfterTransfer(queryClient);
    },
    onError: (failure) => {
      setConfirmCancel(false);
      onFailure(failure);
    },
  });

  const back = (
    <Link to="/stock/transferts" className="text-[0.85rem] font-semibold text-sea hover:underline">
      {t("admin.transfers.back")}
    </Link>
  );

  if (validId && transfer.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!transfer.data) {
    const missing = !validId || (transfer.error instanceof ApiError && transfer.error.status === 404);
    return (
      <>
        {back}
        <EmptyState
          illustration="truck"
          title={missing ? t("admin.transfers.notFound") : t("common.serverUnreachable")}
        />
      </>
    );
  }

  const data = transfer.data;
  const none = t("admin.transfers.detail.none");
  const isDraft = data.status === "draft";
  const canAct = isDraft && canRecordTransfers(session);
  const isLoad = data.kind === "load";
  const truck = truckOf(data);

  return (
    <>
      {back}
      <PageHeader
        eyebrow={`${formatDate(data.transferred_on)} · ${t(`admin.transfers.kinds.${data.kind}`)}`}
        title={data.number}
      >
        <Pill tone={STATUS_TONES[data.status]}>{t(`admin.transfers.statuses.${data.status}`)}</Pill>
        {canAct && (
          <>
            <Button onClick={() => setConfirmCancel(true)}>{t("admin.transfers.detail.cancel")}</Button>
            <Button onClick={() => void navigate(`/stock/transferts/${data.id}/modifier`)}>
              {t("admin.transfers.detail.edit")}
            </Button>
            <Button variant="primary" disabled={validate.isPending} onClick={() => validate.mutate()}>
              <Icon name="check" />
              {validate.isPending ? t("admin.transfers.detail.validating") : t("admin.transfers.detail.validate")}
            </Button>
          </>
        )}
      </PageHeader>

      {isDraft && (
        <div role="note" className="flex items-start gap-3 rounded-card border border-line bg-warn-soft p-3">
          <span className="text-warn">
            <Icon name="alert" />
          </span>
          <span className="text-[0.9rem]">{t("admin.transfers.detail.draftNote")}</span>
        </div>
      )}

      <Card>
        <CardTitle>{t("admin.transfers.detail.transfer")}</CardTitle>
        <dl className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-x-6 gap-y-3">
          <Detail label={t("admin.transfers.detail.from")}>{data.from_location.name}</Detail>
          <Detail label={t("admin.transfers.detail.to")}>
            <span className="inline-flex items-center gap-1.5">
              <Icon name={KIND_ICONS[data.kind]} />
              {data.to_location.name}
            </span>
          </Detail>
          <Detail label={t("admin.transfers.detail.date")} numeric>
            {formatDate(data.transferred_on)}
          </Detail>
          <Detail label={t("admin.transfers.detail.createdBy")}>{data.created_by || none}</Detail>
          {data.validated_at && (
            <>
              <Detail label={t("admin.transfers.detail.validatedBy")}>{data.validated_by || none}</Detail>
              <Detail label={t("admin.transfers.detail.validatedAt")} numeric>
                {formatDateTime(data.validated_at)}
              </Detail>
            </>
          )}
          {data.confirmed_at && (
            <Detail label={t("admin.transfers.detail.confirmedBy")}>
              {data.confirmed_by || none} · {formatDateTime(data.confirmed_at)}
            </Detail>
          )}
          {data.notes && (
            <div className="col-span-full">
              <Detail label={t("admin.transfers.detail.notes")}>
                <span className="whitespace-pre-line">{data.notes}</span>
              </Detail>
            </div>
          )}
        </dl>
      </Card>

      <Card className="p-2">
        <CardTitle className="px-2.5 pt-2">{t("admin.transfers.detail.lines")}</CardTitle>
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.transfers.detail.product")}</Th>
              <Th numeric>{t("admin.transfers.detail.quantity")}</Th>
              {isLoad && <Th numeric>{t("admin.transfers.detail.price")}</Th>}
              {isLoad && <Th numeric>{t("admin.transfers.detail.amount")}</Th>}
              <Th>{t("admin.transfers.detail.batches")}</Th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((line, index) => {
              const error = lineErrors[`lines.${index}.quantity`];
              return (
                <tr key={line.id}>
                  <Td>
                    <span className="font-semibold">{line.product.name}</span>
                    <div className="num text-[0.8rem] text-ink-2">{line.product.reference}</div>
                  </Td>
                  <Td numeric className="font-semibold whitespace-nowrap">
                    {formatQuantity(line.quantity)}
                    {error && <div className="text-[0.78rem] font-semibold whitespace-normal text-bad">{error}</div>}
                  </Td>
                  {isLoad && (
                    <Td numeric className="whitespace-nowrap">
                      {line.unit_price ? formatMoney(line.unit_price) : none}
                    </Td>
                  )}
                  {isLoad && (
                    <Td numeric className="whitespace-nowrap">
                      {line.amount ? formatMoney(line.amount) : none}
                    </Td>
                  )}
                  <Td className="num text-[0.85rem]">
                    {line.batches.length === 0 ? (
                      <span className="text-ink-2">{isDraft ? t("admin.transfers.detail.batchesLater") : none}</span>
                    ) : (
                      line.batches.map((batch) => (
                        <div key={batch.batch_id} className="whitespace-nowrap">
                          {batch.batch_number} · {formatQuantity(batch.quantity)}
                        </div>
                      ))
                    )}
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <dl className="flex flex-wrap justify-end gap-x-8 gap-y-2 border-t border-line px-2.5 py-3">
          <Detail label={t("admin.transfers.detail.totalQuantity")} numeric>
            <b>{formatQuantity(data.total_quantity)}</b>
          </Detail>
          {data.total_amount && (
            <Detail label={t("admin.transfers.detail.totalAmount")} numeric>
              <b>{formatMoney(data.total_amount)}</b>
            </Detail>
          )}
        </dl>
      </Card>

      {truck && <TruckDayCard locationId={truck.id} day={data.transferred_on} />}

      {data.status === "validated" && (
        <p className="text-[0.85rem] text-ink-2">{t("admin.transfers.detail.immutable")}</p>
      )}

      <Dialog open={confirmCancel} onOpenChange={setConfirmCancel}>
        <DialogContent>
          <DialogTitle>{t("admin.transfers.detail.cancelTitle", { number: data.number })}</DialogTitle>
          <DialogDescription>{t("admin.transfers.detail.cancelBody")}</DialogDescription>
          <DialogFooter>
            <Button onClick={() => setConfirmCancel(false)}>{t("admin.transfers.detail.keep")}</Button>
            <Button variant="danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {t("admin.transfers.detail.confirmCancel")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
