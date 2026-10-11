import { addLossPhoto, ApiError, approveLoss, rejectLoss, useGetLoss } from "@frutti/api";
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
  Field,
  Icon,
  PageHeader,
  Pill,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import { fieldErrors } from "../lib/errors";
import { canRecordStockChecks, isOwner, LOSS_TONES, refreshAfterStockCheck } from "./shared";

function Detail({ label, children, numeric = false }: { label: string; children: ReactNode; numeric?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[0.78rem] font-semibold text-ink-2">{label}</dt>
      <dd className={cn("break-words", numeric && "num")}>{children}</dd>
    </div>
  );
}

export function LossDetailPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const queryClient = useQueryClient();
  const { lossId } = useParams();
  const id = Number(lossId);
  const validId = Number.isInteger(id) && id > 0;
  const loss = useGetLoss(id, { query: { enabled: validId, retry: false } });
  const photoId = useId();
  const reasonId = useId();
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectError, setRejectError] = useState("");

  const failed = (failure: unknown) => {
    const fromServer = fieldErrors(failure);
    toast.error(Object.values(fromServer)[0] ?? t("admin.losses.detail.actionError"));
  };
  const approve = useMutation({
    mutationFn: () => approveLoss(id),
    onSuccess: async (saved) => {
      toast.success(t("admin.losses.detail.approved", { number: saved.number }));
      await refreshAfterStockCheck(queryClient);
    },
    onError: failed,
  });
  const reject = useMutation({
    mutationFn: (reason: string) => rejectLoss(id, { reason }),
    onSuccess: async (saved) => {
      setRejecting(false);
      toast.success(t("admin.losses.detail.rejected", { number: saved.number }));
      await refreshAfterStockCheck(queryClient);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setRejectError(fromServer.reason ?? fromServer.detail ?? t("admin.losses.detail.actionError"));
    },
  });
  const photo = useMutation({
    mutationFn: (file: File) => addLossPhoto(id, { photo: file }),
    onSuccess: async () => {
      toast.success(t("admin.losses.detail.photoAdded"));
      await refreshAfterStockCheck(queryClient);
    },
    onError: failed,
  });

  const back = (
    <Link to="/stock/pertes" className="text-[0.85rem] font-semibold text-sea hover:underline">
      {t("admin.losses.back")}
    </Link>
  );

  if (validId && loss.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!loss.data) {
    const missing = !validId || (loss.error instanceof ApiError && loss.error.status === 404);
    return (
      <>
        {back}
        <EmptyState
          illustration="mussel"
          title={missing ? t("admin.losses.notFound") : t("common.serverUnreachable")}
        />
      </>
    );
  }

  const data = loss.data;
  const none = t("admin.losses.detail.none");
  const pending = data.status === "pending";
  const decides = pending && isOwner(session);

  return (
    <>
      {back}
      <PageHeader
        eyebrow={`${formatDate(data.lost_on)} · ${t(`admin.losses.reasons.${data.reason}`)}`}
        title={data.number}
      >
        <Pill tone={LOSS_TONES[data.status]}>{t(`admin.losses.statuses.${data.status}`)}</Pill>
        {decides && (
          <>
            <Button
              onClick={() => {
                setRejectReason("");
                setRejectError("");
                setRejecting(true);
              }}
            >
              {t("admin.losses.detail.reject")}
            </Button>
            <Button variant="primary" disabled={approve.isPending} onClick={() => approve.mutate()}>
              <Icon name="check" />
              {approve.isPending ? t("admin.losses.detail.approving") : t("admin.losses.detail.approve")}
            </Button>
          </>
        )}
      </PageHeader>

      {pending && (
        <div role="note" className="flex items-start gap-3 rounded-card border border-line bg-warn-soft p-3">
          <span className="text-warn">
            <Icon name="alert" />
          </span>
          <span className="text-[0.9rem]">{t("admin.losses.detail.pendingNote")}</span>
        </div>
      )}

      <Card>
        <CardTitle>{t("admin.losses.detail.loss")}</CardTitle>
        <dl className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-x-6 gap-y-3">
          <Detail label={t("admin.losses.detail.product")}>
            <span className="font-semibold">{data.product.name}</span>{" "}
            <span className="num text-[0.85rem] text-ink-2">{data.product.reference}</span>
          </Detail>
          <Detail label={t("admin.losses.detail.quantity")} numeric>
            <b>{formatQuantity(data.quantity)}</b>
          </Detail>
          <Detail label={t("admin.losses.detail.location")}>{data.location.name}</Detail>
          <Detail label={t("admin.losses.detail.reason")}>{t(`admin.losses.reasons.${data.reason}`)}</Detail>
          <Detail label={t("admin.losses.detail.date")} numeric>
            {formatDate(data.lost_on)}
          </Detail>
          <Detail label={t("admin.losses.detail.createdBy")}>{data.created_by || none}</Detail>
          {data.decided_at && (
            <>
              <Detail label={t("admin.losses.detail.decidedBy")}>{data.decided_by || none}</Detail>
              <Detail label={t("admin.losses.detail.decidedAt")} numeric>
                {formatDateTime(data.decided_at)}
              </Detail>
            </>
          )}
          {data.note && (
            <div className="col-span-full">
              <Detail label={t("admin.losses.detail.note")}>
                <span className="whitespace-pre-line">{data.note}</span>
              </Detail>
            </div>
          )}
          {data.rejection_reason && (
            <div className="col-span-full">
              <Detail label={t("admin.losses.detail.rejection")}>
                <span className="whitespace-pre-line">{data.rejection_reason}</span>
              </Detail>
            </div>
          )}
        </dl>
      </Card>

      <Card className="flex flex-col gap-3">
        <CardTitle className="mb-0">{t("admin.losses.detail.photo")}</CardTitle>
        {data.photo_url ? (
          <img
            src={data.photo_url}
            alt={t("admin.losses.detail.photoAlt", { number: data.number })}
            className="max-h-80 w-auto self-start rounded-card border border-line object-contain"
          />
        ) : (
          <>
            <p className="text-ink-2">{t("admin.losses.detail.noPhoto")}</p>
            {canRecordStockChecks(session) && (
              <Field label={t("admin.losses.detail.addPhoto")} htmlFor={photoId}>
                <input
                  id={photoId}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={photo.isPending}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) photo.mutate(file);
                  }}
                  className="self-start rounded-control border border-line bg-surface px-3 py-2 text-[0.9rem] text-ink"
                />
              </Field>
            )}
          </>
        )}
      </Card>

      {data.batches.length > 0 && (
        <Card className="p-2">
          <CardTitle className="px-2.5 pt-2">{t("admin.losses.detail.batches")}</CardTitle>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.losses.detail.batch")}</Th>
                <Th numeric>{t("admin.losses.detail.batchQuantity")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.batches.map((batch) => (
                <tr key={batch.batch_id}>
                  <Td className="num">{batch.batch_number}</Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatQuantity(batch.quantity)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
          {data.cost_amount && (
            <dl className="flex justify-end border-t border-line px-2.5 py-3">
              <Detail label={t("admin.losses.detail.cost")} numeric>
                <b>{formatMoney(data.cost_amount)}</b>
              </Detail>
            </dl>
          )}
        </Card>
      )}

      {!pending && <p className="text-[0.85rem] text-ink-2">{t("admin.losses.detail.immutable")}</p>}

      <Dialog open={rejecting} onOpenChange={setRejecting}>
        <DialogContent>
          <DialogTitle>{t("admin.losses.detail.rejectTitle", { number: data.number })}</DialogTitle>
          <DialogDescription>{t("admin.losses.detail.rejectBody")}</DialogDescription>
          <form
            noValidate
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              reject.mutate(rejectReason);
            }}
          >
            <Field label={t("admin.losses.detail.rejectReason")} htmlFor={reasonId} error={rejectError}>
              <textarea
                id={reasonId}
                rows={2}
                value={rejectReason}
                onChange={(event) => setRejectReason(event.target.value)}
                className="w-full rounded-control border border-line bg-surface px-3 py-2.5 text-ink"
              />
            </Field>
            <DialogFooter>
              <Button onClick={() => setRejecting(false)}>{t("admin.losses.detail.keep")}</Button>
              <Button type="submit" variant="danger" disabled={reject.isPending}>
                {t("admin.losses.detail.confirmReject")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
