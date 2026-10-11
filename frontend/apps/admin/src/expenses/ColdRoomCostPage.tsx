import {
  approveElectricityBill,
  type ColdRoomWeight,
  createElectricityBill,
  deleteElectricityBill,
  type ElectricityBill,
  type PaymentMethodEnum,
  updateColdRoomWeight,
  useGetColdRoomMonth,
  useListColdRoomWeights,
  useListElectricityBills,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatMoney, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, CardTitle, EmptyState, Field, Input, PageHeader, Pill, Table, Td, Th, toast } from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import { useOutletContext } from "react-router";

import { fieldErrors } from "../lib/errors";
import { currentMonth, monthLabel, shiftMonth } from "../hr/shared";
import { CostSelect } from "./CostSelect";
import { ExpensesTabs } from "./ExpensesTabs";
import { canManageCategories, canWriteExpenses, EXPENSE_TONES, PAYMENT_METHODS, refreshExpenses } from "./shared";

type Errors = Record<string, string>;

/** Type the month's electricity bill (a finished month): draft, or approved at once. */
function BillForm({ month, onDone }: { month: string; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const formId = useId();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethodEnum>("transfer");
  const [payee, setPayee] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const save = useMutation({
    mutationFn: (approve: boolean) => {
      const parsed = parseDecimalInput(amount.trim(), 3);
      if (!parsed || parsed.startsWith("-") || /^0+(\.0+)?$/.test(parsed)) throw new Error("amount");
      return createElectricityBill({
        month,
        amount: parsed,
        payment_method: method,
        payee: payee.trim(),
        approve_now: approve,
      });
    },
    onSuccess: async (bill) => {
      toast.success(bill.finalized ? t("admin.coldCost.bill.approved") : t("admin.coldCost.bill.saved"));
      await refreshExpenses(queryClient);
      onDone();
    },
    onError: (failure) => {
      if (failure instanceof Error && failure.message === "amount") {
        setErrors({ amount: t("admin.coldCost.bill.amountInvalid") });
        return;
      }
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.coldCost.bill.error") });
    },
  });

  const id = (name: string) => `${formId}-${name}`;
  function submit(approve: boolean) {
    return (event: FormEvent) => {
      event.preventDefault();
      setErrors({});
      save.mutate(approve);
    };
  }
  return (
    <form noValidate onSubmit={submit(false)} className="flex flex-col gap-3">
      <p className="text-ink-2">{t("admin.coldCost.bill.none")}</p>
      <div className="grid grid-cols-3 gap-4 max-[720px]:grid-cols-1">
        <Field label={t("admin.coldCost.bill.amount")} htmlFor={id("amount")} error={errors.amount}>
          <Input
            id={id("amount")}
            inputMode="decimal"
            className="num"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            aria-invalid={errors.amount ? true : undefined}
            autoComplete="off"
          />
        </Field>
        <CostSelect
          id={id("method")}
          label={t("admin.coldCost.bill.method")}
          value={method}
          onChange={(value) => setMethod(value as PaymentMethodEnum)}
          options={PAYMENT_METHODS.map((value) => ({ value, label: t(`admin.expenses.methods.${value}`) }))}
          placeholder={t("admin.generalCosts.dialog.choose")}
          error={errors.payment_method}
        />
        <Field label={t("admin.coldCost.bill.payee")} htmlFor={id("payee")} error={errors.payee}>
          <Input id={id("payee")} value={payee} onChange={(event) => setPayee(event.target.value)} autoComplete="off" />
        </Field>
      </div>
      {(errors.detail || errors.month) && (
        <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
          {errors.detail ?? errors.month}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={save.isPending}>
          {t("admin.coldCost.bill.save")}
        </Button>
        <Button type="button" variant="primary" disabled={save.isPending} onClick={submit(true)}>
          {t("admin.coldCost.bill.saveAndApprove")}
        </Button>
      </div>
    </form>
  );
}

/** The bill of the month once typed: its state, and approve / delete while it is a draft. */
function BillSummary({ bill, canWrite }: { bill: ElectricityBill; canWrite: boolean }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const approve = useMutation({
    mutationFn: () => approveElectricityBill(bill.id),
    onSuccess: async () => {
      toast.success(t("admin.coldCost.bill.approved"));
      await refreshExpenses(queryClient);
    },
    onError: (failure) => toast.error(Object.values(fieldErrors(failure))[0] ?? t("admin.coldCost.bill.error")),
  });
  const remove = useMutation({
    mutationFn: () => deleteElectricityBill(bill.id),
    onSuccess: async () => {
      toast.success(t("admin.coldCost.bill.deleted"));
      await refreshExpenses(queryClient);
    },
    onError: () => toast.error(t("admin.coldCost.bill.error")),
  });
  const draft = bill.status === "draft";
  return (
    <div className="flex flex-col gap-2">
      <p className="flex flex-wrap items-center gap-2">
        <b className="num text-[1.1rem]">{formatMoney(bill.amount)}</b>
        <span className="text-ink-2">{bill.expense_number}</span>
        <Pill tone={EXPENSE_TONES[bill.status]}>{t(`admin.coldCost.bill.statuses.${bill.status}`)}</Pill>
      </p>
      <p className="text-[0.88rem] text-ink-2">
        {draft ? t("admin.coldCost.bill.draftHint") : t("admin.coldCost.bill.approvedHint")}
      </p>
      {draft && canWrite && (
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" disabled={approve.isPending || remove.isPending} onClick={() => approve.mutate()}>
            {t("admin.coldCost.bill.approve")}
          </Button>
          <Button disabled={approve.isPending || remove.isPending} onClick={() => remove.mutate()}>
            {t("admin.coldCost.bill.delete")}
          </Button>
        </div>
      )}
    </div>
  );
}

/** One row of the weights table: the owner types a weight and saves it. */
function WeightRow({ room, canEdit }: { room: ColdRoomWeight; canEdit: boolean }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [weight, setWeight] = useState(room.weight.replace(".", ","));
  const [error, setError] = useState("");
  const save = useMutation({
    mutationFn: () => {
      const parsed = parseDecimalInput(weight.trim(), 3);
      if (!parsed || parsed.startsWith("-") || /^0+(\.0+)?$/.test(parsed)) throw new Error("weight");
      return updateColdRoomWeight(room.location_id, { weight: parsed });
    },
    onSuccess: async () => {
      setError("");
      toast.success(t("admin.coldCost.weights.saved", { room: room.location_name }));
      await refreshExpenses(queryClient);
    },
    onError: () => setError(t("admin.coldCost.weights.invalid")),
  });
  return (
    <tr>
      <Td className="font-semibold">{room.location_name}</Td>
      <Td numeric>
        {canEdit ? (
          <Input
            aria-label={t("admin.coldCost.weights.weightOf", { room: room.location_name })}
            inputMode="decimal"
            className="num w-24 text-end"
            value={weight}
            onChange={(event) => setWeight(event.target.value)}
            aria-invalid={error ? true : undefined}
            autoComplete="off"
          />
        ) : (
          <span className="num">{room.weight.replace(".", ",")}</span>
        )}
        {error && <div className="text-[0.8rem] text-bad">{error}</div>}
      </Td>
      <Td numeric className="num">
        {room.share_percent.replace(".", ",")} %
      </Td>
      {canEdit && (
        <Td>
          <Button variant="ghost" disabled={save.isPending} onClick={() => save.mutate()}>
            {t("admin.coldCost.weights.save")}
          </Button>
        </Td>
      )}
    </tr>
  );
}

/** "Chambres froides : coût": the month's electricity bill, what each room costs per day (estimated until the
 * bill is approved) and the weight of each room (P5-T02, D-058). */
export function ColdRoomCostPage() {
  const { t, i18n } = useTranslation();
  const session = useOutletContext<Session>();
  const canWrite = canWriteExpenses(session);
  const isOwner = canManageCategories(session);
  const [month, setMonth] = useState(() => shiftMonth(currentMonth(), -1));
  const view = useGetColdRoomMonth({ month });
  const weights = useListColdRoomWeights();
  const bills = useListElectricityBills();
  const [reload, setReload] = useState(0);
  const finished = month < currentMonth();
  const label = monthLabel(month, i18n.language);
  const data = view.data;

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.finance")} title={t("admin.coldCost.title")} />
      <ExpensesTabs />
      <p className="text-ink-2">{t("admin.coldCost.intro")}</p>
      {!canWrite && <p className="text-[0.88rem] text-ink-2">{t("admin.coldCost.readOnly")}</p>}

      <Card className="flex flex-wrap items-center gap-2 p-3">
        <span className="me-auto font-semibold">{t("admin.coldCost.monthNav")}</span>
        <Button
          variant="ghost"
          aria-label={t("admin.coldCost.previous")}
          onClick={() => setMonth(shiftMonth(month, -1))}
        >
          ‹
        </Button>
        <b className="min-w-36 text-center capitalize" aria-live="polite">
          {label}
        </b>
        <Button
          variant="ghost"
          aria-label={t("admin.coldCost.next")}
          disabled={month >= currentMonth()}
          onClick={() => setMonth(shiftMonth(month, 1))}
        >
          ›
        </Button>
      </Card>

      <section aria-labelledby="cold-bill" className="flex flex-col gap-2">
        <h2 id="cold-bill">{t("admin.coldCost.bill.title", { month: label })}</h2>
        <Card className="flex flex-col gap-3 p-4">
          {view.isPending ? (
            <p className="text-ink-2">{t("common.loading")}</p>
          ) : !data ? (
            <p role="alert" className="text-bad">
              {t("common.serverUnreachable")}
            </p>
          ) : data.bill ? (
            <BillSummary key={`${data.bill.id}-${data.bill.status}-${reload}`} bill={data.bill} canWrite={canWrite} />
          ) : !finished ? (
            <p className="text-ink-2">{t("admin.coldCost.bill.notYet")}</p>
          ) : canWrite ? (
            <BillForm key={month} month={month} onDone={() => setReload(reload + 1)} />
          ) : (
            <p className="text-ink-2">{t("admin.coldCost.bill.none")}</p>
          )}
        </Card>
      </section>

      <section aria-labelledby="cold-rooms" className="flex flex-col gap-2">
        <h2 id="cold-rooms">{t("admin.coldCost.rooms.title")}</h2>
        {data && data.rooms.length === 0 ? (
          <EmptyState illustration="fridge" title={t("admin.coldCost.rooms.noRooms")}>
            {t("admin.coldCost.rooms.noRoomsBody")}
          </EmptyState>
        ) : (
          data && (
            <Card className="p-2">
              <Table>
                <thead>
                  <tr>
                    <Th>{t("admin.coldCost.rooms.room")}</Th>
                    <Th numeric>{t("admin.coldCost.rooms.weight")}</Th>
                    <Th numeric>{t("admin.coldCost.rooms.month")}</Th>
                    <Th numeric>{t("admin.coldCost.rooms.day")}</Th>
                    <Th>{t("admin.coldCost.rooms.kind")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.rooms.map((row) => (
                    <tr key={row.location_id}>
                      <Td className="font-semibold">{row.location_name}</Td>
                      <Td numeric className="num">
                        {row.weight.replace(".", ",")}
                      </Td>
                      <Td numeric className="whitespace-nowrap">
                        {row.month_amount !== null ? formatMoney(row.month_amount) : t("admin.coldCost.rooms.unknown")}
                      </Td>
                      <Td numeric className="whitespace-nowrap">
                        {row.day_amount !== null ? formatMoney(row.day_amount) : t("admin.coldCost.rooms.unknown")}
                      </Td>
                      <Td>
                        <Pill tone={row.estimated ? "warn" : "good"}>
                          {row.estimated ? t("admin.coldCost.rooms.estimated") : t("admin.coldCost.rooms.real")}
                        </Pill>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <p className="flex justify-end gap-2 border-t border-line px-2.5 py-3">
                {t("admin.coldCost.rooms.total")}{" "}
                <b className="num">
                  {data.total !== null ? formatMoney(data.total) : t("admin.coldCost.rooms.unknown")}
                </b>
              </p>
              {data.estimated && (
                <p className="px-2.5 pb-2 text-[0.85rem] text-ink-2">
                  {data.estimate_source_month
                    ? t("admin.coldCost.rooms.estimateFrom", {
                        month: monthLabel(data.estimate_source_month, i18n.language),
                      })
                    : t("admin.coldCost.rooms.noEstimate")}
                </p>
              )}
            </Card>
          )
        )}
      </section>

      <section aria-labelledby="cold-weights" className="flex flex-col gap-2">
        <h2 id="cold-weights">{t("admin.coldCost.weights.title")}</h2>
        <p className="text-ink-2">{t("admin.coldCost.weights.body")}</p>
        {!isOwner && <p className="text-[0.85rem] text-ink-2">{t("admin.coldCost.weights.ownerOnly")}</p>}
        <Card className="p-2">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.coldCost.rooms.room")}</Th>
                <Th numeric>{t("admin.coldCost.rooms.weight")}</Th>
                <Th numeric>{t("admin.coldCost.rooms.share")}</Th>
                {isOwner && <Th className="w-0" />}
              </tr>
            </thead>
            <tbody>
              {(weights.data ?? []).map((room) => (
                <WeightRow key={`${room.location_id}-${room.weight}`} room={room} canEdit={isOwner} />
              ))}
            </tbody>
          </Table>
        </Card>
      </section>

      <section aria-labelledby="cold-bills" className="flex flex-col gap-2">
        <CardTitle id="cold-bills" className="text-[1rem]">
          {t("admin.coldCost.bills.title")}
        </CardTitle>
        {(bills.data ?? []).length === 0 ? (
          <p className="text-ink-2">{t("admin.coldCost.bills.empty")}</p>
        ) : (
          <Card className="p-2">
            <Table>
              <thead>
                <tr>
                  <Th>{t("admin.coldCost.bills.month")}</Th>
                  <Th numeric>{t("admin.coldCost.bills.amount")}</Th>
                  <Th>{t("admin.coldCost.bills.status")}</Th>
                </tr>
              </thead>
              <tbody>
                {(bills.data ?? []).map((bill) => (
                  <tr key={bill.id}>
                    <Td className="capitalize">
                      <button type="button" className="text-sea hover:underline" onClick={() => setMonth(bill.month)}>
                        {monthLabel(bill.month, i18n.language)}
                      </button>
                    </Td>
                    <Td numeric className="whitespace-nowrap">
                      {formatMoney(bill.amount)}
                    </Td>
                    <Td>
                      <Pill tone={EXPENSE_TONES[bill.status]}>{t(`admin.coldCost.bill.statuses.${bill.status}`)}</Pill>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        )}
      </section>
    </>
  );
}
