import { ApiError, approveCount, cancelCount, type Count, recordCounted, useGetCount } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatDateTime, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
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
  Input,
  PageHeader,
  Pill,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { Link, useOutletContext, useParams } from "react-router";

import { subtract, sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { canRecordStockChecks, COUNT_TONES, refreshAfterStockCheck } from "../losses/shared";

const asTyped = (value: string) => value.replace(".", ",");
const isZero = (value: string) => /^-?0+(\.0+)?$/.test(value);

function Detail({ label, children, numeric = false }: { label: string; children: ReactNode; numeric?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[0.78rem] font-semibold text-ink-2">{label}</dt>
      <dd className={cn("break-words", numeric && "num")}>{children}</dd>
    </div>
  );
}

/** "+0,400 kg" in green, "−1,400 kg" in red, nothing when equal. */
function Difference({ value }: { value: string | null }) {
  if (value === null) return null;
  if (isZero(value)) return <span className="text-ink-2">{formatQuantity("0")}</span>;
  const negative = value.startsWith("-");
  return (
    <span className={cn("font-semibold", negative ? "text-bad" : "text-good")}>
      {negative ? "" : "+"}
      {formatQuantity(value)}
    </span>
  );
}

export function CountPage() {
  const { t } = useTranslation();
  const { countId } = useParams();
  const id = Number(countId);
  const validId = Number.isInteger(id) && id > 0;
  const count = useGetCount(id, { query: { enabled: validId, retry: false } });

  const back = (
    <Link to="/stock/inventaires" className="text-[0.85rem] font-semibold text-sea hover:underline">
      {t("admin.counts.back")}
    </Link>
  );
  if (validId && count.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!count.data) {
    const missing = !validId || (count.error instanceof ApiError && count.error.status === 404);
    return (
      <>
        {back}
        <EmptyState
          illustration="fridge"
          title={missing ? t("admin.counts.notFound") : t("common.serverUnreachable")}
        />
      </>
    );
  }
  // A new key after each save starts the inputs again from what the server kept.
  return <CountSheet key={`${count.data.id}-${count.dataUpdatedAt}`} data={count.data} back={back} />;
}

function CountSheet({ data, back }: { data: Count; back: ReactNode }) {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const queryClient = useQueryClient();
  const [typed, setTyped] = useState<Record<number, string>>(() =>
    Object.fromEntries(
      data.lines.map((line) => [line.id, line.counted_quantity ? asTyped(line.counted_quantity) : ""]),
    ),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmCancel, setConfirmCancel] = useState(false);
  const open = data.status === "counting";
  const canAct = open && canRecordStockChecks(session);

  /** The typed weights as the API takes them, or null after showing what is wrong. */
  function payload() {
    const found: Record<string, string> = {};
    const lines = data.lines.map((line, index) => {
      const text = (typed[line.id] ?? "").trim();
      if (text === "") return { line: line.id, counted_quantity: null };
      const parsed = parseDecimalInput(text, 3);
      if (parsed === null || parsed.startsWith("-"))
        found[`lines.${index}.counted_quantity`] = t("admin.counts.sheet.weight");
      return { line: line.id, counted_quantity: parsed };
    });
    setErrors(found);
    return Object.keys(found).length > 0 ? null : lines;
  }

  const failed = (failure: unknown) => {
    const fromServer = fieldErrors(failure);
    setErrors(fromServer);
    const general = fromServer.detail ?? fromServer.lines;
    if (general || Object.keys(fromServer).length === 0) toast.error(general ?? t("admin.counts.sheet.actionError"));
  };
  const save = useMutation({
    mutationFn: async ({ lines, approve }: { lines: NonNullable<ReturnType<typeof payload>>; approve: boolean }) => {
      const saved = await recordCounted(data.id, { lines });
      return approve ? approveCount(data.id) : saved;
    },
    onSuccess: async (saved) => {
      toast.success(
        saved.status === "approved"
          ? t("admin.counts.sheet.approved", { number: saved.number })
          : t("admin.counts.sheet.saved"),
      );
      await refreshAfterStockCheck(queryClient);
    },
    // The weights may already be saved when the approval is refused; the inputs keep them as typed.
    onError: failed,
  });
  const cancel = useMutation({
    mutationFn: () => cancelCount(data.id),
    onSuccess: async (saved) => {
      setConfirmCancel(false);
      toast.success(t("admin.counts.sheet.cancelled", { number: saved.number }));
      await refreshAfterStockCheck(queryClient);
    },
    onError: (failure) => {
      setConfirmCancel(false);
      failed(failure);
    },
  });

  const differenceOf = (lineId: number, expected: string, saved: string | null): string | null => {
    if (!open) return saved;
    const parsed = parseDecimalInput((typed[lineId] ?? "").trim(), 3);
    return parsed === null || parsed.startsWith("-") ? null : subtract(parsed, expected);
  };
  const differences = data.lines.map((line) => differenceOf(line.id, line.expected_quantity, line.difference));
  const total = sum(differences.flatMap((value) => (value ? [value] : [])));
  const none = t("admin.counts.sheet.none");

  return (
    <>
      {back}
      <PageHeader eyebrow={`${formatDate(data.counted_on)} · ${data.location.name}`} title={data.number}>
        <Pill tone={COUNT_TONES[data.status]}>{t(`admin.counts.statuses.${data.status}`)}</Pill>
        {canAct && (
          <>
            <Button onClick={() => setConfirmCancel(true)}>{t("admin.counts.sheet.cancel")}</Button>
            <Button
              disabled={save.isPending}
              onClick={() => {
                const lines = payload();
                if (lines) save.mutate({ lines, approve: false });
              }}
            >
              {save.isPending ? t("admin.counts.sheet.saving") : t("admin.counts.sheet.save")}
            </Button>
            <Button
              variant="primary"
              disabled={save.isPending}
              onClick={() => {
                const lines = payload();
                if (lines) save.mutate({ lines, approve: true });
              }}
            >
              <Icon name="check" />
              {t("admin.counts.sheet.approve")}
            </Button>
          </>
        )}
      </PageHeader>

      {open && (
        <div role="note" className="flex items-start gap-3 rounded-card border border-line bg-warn-soft p-3">
          <span className="text-warn">
            <Icon name="scale" />
          </span>
          <span className="text-[0.9rem]">{t("admin.counts.sheet.intro")}</span>
        </div>
      )}

      <Card>
        <dl className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-x-6 gap-y-3">
          <Detail label={t("admin.counts.sheet.location")}>{data.location.name}</Detail>
          <Detail label={t("admin.counts.sheet.date")} numeric>
            {formatDate(data.counted_on)}
          </Detail>
          <Detail label={t("admin.counts.sheet.createdBy")}>{data.created_by || none}</Detail>
          {data.approved_at && (
            <>
              <Detail label={t("admin.counts.sheet.approvedBy")}>{data.approved_by || none}</Detail>
              <Detail label={t("admin.counts.sheet.approvedAt")} numeric>
                {formatDateTime(data.approved_at)}
              </Detail>
            </>
          )}
          {data.notes && (
            <div className="col-span-full">
              <Detail label={t("admin.counts.sheet.notes")}>{data.notes}</Detail>
            </div>
          )}
        </dl>
      </Card>

      <Card className="p-2">
        <div className="flex flex-wrap items-center gap-3 px-2.5 pt-2">
          <CardTitle className="mb-0">{t("admin.counts.columns.lines")}</CardTitle>
          {canAct && (
            <Button
              className="ms-auto"
              title={t("admin.counts.sheet.fillExpectedHint")}
              onClick={() =>
                setTyped((current) =>
                  Object.fromEntries(
                    data.lines.map((line) => {
                      const value = current[line.id] ?? "";
                      return [line.id, value.trim() === "" ? asTyped(line.expected_quantity) : value];
                    }),
                  ),
                )
              }
            >
              {t("admin.counts.sheet.fillExpected")}
            </Button>
          )}
        </div>
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.counts.sheet.product")}</Th>
              <Th>{t("admin.counts.sheet.batch")}</Th>
              <Th numeric>{t("admin.counts.sheet.expected")}</Th>
              <Th numeric>{t("admin.counts.sheet.counted")}</Th>
              <Th numeric>{t("admin.counts.sheet.difference")}</Th>
            </tr>
          </thead>
          <tbody>
            {data.lines.map((line, index) => {
              const error = errors[`lines.${index}.counted_quantity`];
              return (
                <tr key={line.id}>
                  <Td>
                    <span className="font-semibold">{line.product.name}</span>
                    <div className="num text-[0.8rem] text-ink-2">{line.product.reference}</div>
                  </Td>
                  <Td className="num whitespace-nowrap">
                    {line.batch.number}
                    <div className="text-[0.8rem] text-ink-2">{formatDate(line.batch.received_on)}</div>
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatQuantity(line.expected_quantity)}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {open ? (
                      <>
                        <Input
                          inputMode="decimal"
                          aria-label={t("admin.counts.sheet.countedOf", {
                            product: line.product.name,
                            batch: line.batch.number,
                          })}
                          value={typed[line.id] ?? ""}
                          disabled={!canAct}
                          onChange={(event) => setTyped((current) => ({ ...current, [line.id]: event.target.value }))}
                          aria-invalid={error ? true : undefined}
                          className="num ms-auto w-28 text-end"
                        />
                        {error && (
                          <div className="text-[0.78rem] font-semibold whitespace-normal text-bad">{error}</div>
                        )}
                      </>
                    ) : line.counted_quantity ? (
                      formatQuantity(line.counted_quantity)
                    ) : (
                      none
                    )}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    <Difference value={differences[index] ?? null} />
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
        <dl className="flex justify-end border-t border-line px-2.5 py-3">
          <Detail label={t("admin.counts.sheet.totalDifference")} numeric>
            <Difference value={total} />
          </Detail>
        </dl>
      </Card>

      {data.status === "approved" && <p className="text-[0.85rem] text-ink-2">{t("admin.counts.sheet.immutable")}</p>}

      <Dialog open={confirmCancel} onOpenChange={setConfirmCancel}>
        <DialogContent>
          <DialogTitle>{t("admin.counts.sheet.cancelTitle", { number: data.number })}</DialogTitle>
          <DialogDescription>{t("admin.counts.sheet.cancelBody")}</DialogDescription>
          <DialogFooter>
            <Button onClick={() => setConfirmCancel(false)}>{t("admin.counts.sheet.keep")}</Button>
            <Button variant="danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {t("admin.counts.sheet.confirmCancel")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
