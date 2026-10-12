import {
  type DayClosingRow,
  useApproveDayClosing,
  useGetDayClosing,
  useListDayClosings,
  useListSyncProblems,
  useResolveSyncProblem,
  useRequestDayJustification,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  cn,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  EmptyState,
  Input,
  PageHeader,
  Pill,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useOutletContext } from "react-router";

const STATUSES = ["submitted", "justification", "approved"] as const;
const TONES = { submitted: "warn", justification: "bad", approved: "good" } as const;

function signed(value: string): string {
  return `${Number(value) > 0 ? "+" : ""}${formatMoney(value)}`;
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <p className="flex justify-between gap-3">
      <span className="text-ink-2">{label}</span>
      <span className="num font-semibold">{value}</span>
    </p>
  );
}

function ClosingDialog({ id, canDecide, onDone }: { id: number; canDecide: boolean; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const closing = useGetDayClosing(id);
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const refresh = () => {
    void queryClient.invalidateQueries();
  };
  const approve = useApproveDayClosing({
    mutation: {
      onSuccess: () => {
        toast.success(t("admin.dayClosings.approved"));
        refresh();
        onDone();
      },
      onError: () => toast.error(t("admin.dayClosings.error")),
    },
  });
  const ask = useRequestDayJustification({
    mutation: {
      onSuccess: () => {
        toast.success(t("admin.dayClosings.asked"));
        refresh();
        onDone();
      },
      onError: () => toast.error(t("admin.dayClosings.error")),
    },
  });
  const data = closing.data;
  return (
    <DialogContent>
      <DialogTitle>{data ? `${data.truck_name} · ${formatDate(data.date)}` : t("common.loading")}</DialogTitle>
      <DialogDescription>{data?.driver_name ?? ""}</DialogDescription>
      {data && (
        <div className="flex flex-col gap-4">
          <div className="space-y-1">
            <Line
              label={t("admin.dayClosings.sales", { count: data.summary.sales_count })}
              value={formatMoney(data.summary.sales_total)}
            />
            <Line label={t("admin.dayClosings.cash")} value={formatMoney(data.summary.cash_received)} />
            <Line label={t("admin.dayClosings.payments")} value={formatMoney(data.summary.payments_cash ?? "0.000")} />
            <Line label={t("admin.dayClosings.other")} value={formatMoney(data.summary.other_payments)} />
            <Line label={t("admin.dayClosings.credit")} value={formatMoney(data.summary.on_credit)} />
            <Line label={t("admin.dayClosings.expenses")} value={formatMoney(data.summary.expenses_total)} />
            <Line label={t("admin.dayClosings.opening")} value={formatMoney(data.summary.opening_cash)} />
            <Line label={t("admin.dayClosings.expected")} value={formatMoney(data.expected_cash)} />
            <Line label={t("admin.dayClosings.counted")} value={formatMoney(data.counted_cash)} />
            <Line label={t("admin.dayClosings.difference")} value={signed(data.difference)} />
          </div>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.dayClosings.product")}</Th>
                <Th className="text-end">{t("admin.dayClosings.loaded")}</Th>
                <Th className="text-end">{t("admin.dayClosings.sold")}</Th>
                <Th className="text-end">{t("admin.dayClosings.lost")}</Th>
                <Th className="text-end">{t("admin.dayClosings.returned")}</Th>
                <Th className="text-end">{t("admin.dayClosings.left")}</Th>
              </tr>
            </thead>
            <tbody>
              {data.summary.products.map((product) => (
                <tr key={product.product_id}>
                  <Td>{product.product_name}</Td>
                  <Td className="num text-end">{formatQuantity(product.loaded)}</Td>
                  <Td className="num text-end">{formatQuantity(product.sold)}</Td>
                  <Td className="num text-end">{formatQuantity(product.lost)}</Td>
                  <Td className="num text-end">{formatQuantity(product.returned)}</Td>
                  <Td className="num text-end">{formatQuantity(product.remaining)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          {data.driver_note !== "" && (
            <p>
              <span className="text-ink-2">{t("admin.dayClosings.driverNote")} : </span>
              {data.driver_note}
            </p>
          )}
          {data.review_note !== "" && (
            <p>
              <span className="text-ink-2">{t("admin.dayClosings.reviewNote")} : </span>
              {data.review_note}
            </p>
          )}
          {canDecide && data.status === "submitted" && asking && (
            <Input
              aria-label={t("admin.dayClosings.reason")}
              placeholder={t("admin.dayClosings.reason")}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          )}
        </div>
      )}
      <DialogFooter>
        <Button onClick={onDone}>{t("admin.dayClosings.close")}</Button>
        {canDecide && data?.status === "submitted" && (
          <>
            {asking ? (
              <Button
                disabled={reason.trim() === "" || ask.isPending}
                onClick={() => ask.mutate({ closingId: id, data: { reason } })}
              >
                {t("admin.dayClosings.sendQuestion")}
              </Button>
            ) : (
              <Button onClick={() => setAsking(true)}>{t("admin.dayClosings.askWhy")}</Button>
            )}
            <Button variant="primary" disabled={approve.isPending} onClick={() => approve.mutate({ closingId: id })}>
              {t("admin.dayClosings.approve")}
            </Button>
          </>
        )}
      </DialogFooter>
    </DialogContent>
  );
}

function SyncProblems({ canDecide }: { canDecide: boolean }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const problems = useListSyncProblems();
  const resolve = useResolveSyncProblem({
    mutation: {
      onSuccess: () => {
        toast.success(t("admin.dayClosings.problems.handled"));
        void queryClient.invalidateQueries();
      },
      onError: () => toast.error(t("admin.dayClosings.error")),
    },
  });
  const list = problems.data ?? [];
  if (list.length === 0) return null;
  return (
    <Card className="p-2">
      <h2 className="px-3 pt-2">{t("admin.dayClosings.problems.title")}</h2>
      <p className="px-3 pb-2 text-ink-2">{t("admin.dayClosings.problems.body")}</p>
      <Table>
        <thead>
          <tr>
            <Th>{t("admin.dayClosings.date")}</Th>
            <Th>{t("admin.dayClosings.problems.driver")}</Th>
            <Th>{t("admin.dayClosings.problems.what")}</Th>
            <Th>{t("admin.dayClosings.problems.reason")}</Th>
            {canDecide && <Th />}
          </tr>
        </thead>
        <tbody>
          {list.map((problem) => (
            <tr key={problem.id}>
              <Td>{formatDate(problem.created_at)}</Td>
              <Td>{problem.driver_name}</Td>
              <Td>
                {t(`admin.dayClosings.problems.kinds.${problem.kind as "sale" | "expense" | "loss"}`)} · {problem.label}
              </Td>
              <Td>{problem.reason}</Td>
              {canDecide && (
                <Td>
                  <Button disabled={resolve.isPending} onClick={() => resolve.mutate({ problemId: problem.id })}>
                    {t("admin.dayClosings.problems.done")}
                  </Button>
                </Td>
              )}
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

/** "Journées des chauffeurs": the days drivers sent, to check and approve (P3-T06). */
export function DayClosingsPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const canDecide = session.role === "owner" || session.role === "manager";
  const [status, setStatus] = useState<(typeof STATUSES)[number] | "">("submitted");
  const [open, setOpen] = useState<number | null>(null);
  const closings = useListDayClosings(status ? { status } : {});
  const list: readonly DayClosingRow[] = closings.data ?? [];

  const statusButton = (value: (typeof STATUSES)[number] | "", label: string) => (
    <button
      key={value || "all"}
      type="button"
      aria-pressed={status === value}
      onClick={() => setStatus(value)}
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
      <PageHeader eyebrow={t("admin.groups.goods")} title={t("admin.dayClosings.title")} />
      <SyncProblems canDecide={canDecide} />
      <Card className="filter-bar flex flex-wrap items-center gap-3 p-3">
        <div
          role="group"
          aria-label={t("admin.dayClosings.statusFilter")}
          className="flex rounded-control bg-surface-2 p-1"
        >
          {STATUSES.map((value) => statusButton(value, t(`admin.dayClosings.statuses.${value}`)))}
          {statusButton("", t("admin.dayClosings.all"))}
        </div>
      </Card>
      {closings.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : closings.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : list.length === 0 ? (
        <EmptyState illustration="truck" title={t("admin.dayClosings.empty")}>
          {t("admin.dayClosings.emptyBody")}
        </EmptyState>
      ) : (
        <Card className="p-2">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.dayClosings.date")}</Th>
                <Th>{t("admin.dayClosings.truck")}</Th>
                <Th>{t("admin.dayClosings.driver")}</Th>
                <Th className="text-end">{t("admin.dayClosings.expected")}</Th>
                <Th className="text-end">{t("admin.dayClosings.counted")}</Th>
                <Th className="text-end">{t("admin.dayClosings.difference")}</Th>
                <Th>{t("admin.dayClosings.status")}</Th>
              </tr>
            </thead>
            <tbody>
              {list.map((row) => (
                <tr key={row.id} className="cursor-pointer hover:bg-surface-2" onClick={() => setOpen(row.id)}>
                  <Td>
                    <button type="button" className="font-semibold" onClick={() => setOpen(row.id)}>
                      {formatDate(row.date)}
                    </button>
                  </Td>
                  <Td>{row.truck_name}</Td>
                  <Td>{row.driver_name}</Td>
                  <Td className="num text-end">{formatMoney(row.expected_cash)}</Td>
                  <Td className="num text-end">{formatMoney(row.counted_cash)}</Td>
                  <Td className="num text-end">{signed(row.difference)}</Td>
                  <Td>
                    <Pill tone={TONES[row.status]}>{t(`admin.dayClosings.statuses.${row.status}`)}</Pill>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      <Dialog open={open !== null} onOpenChange={(value) => !value && setOpen(null)}>
        {open !== null && <ClosingDialog id={open} canDecide={canDecide} onDone={() => setOpen(null)} />}
      </Dialog>
    </>
  );
}
