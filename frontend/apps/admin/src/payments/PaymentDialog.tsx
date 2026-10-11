import { createCustomerPayment, type SalePaymentMethodEnum } from "@frutti/api";
import { formatMoney, parseDecimalInput, useTranslation } from "@frutti/i18n";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  Field,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { fieldErrors } from "../lib/errors";
import { PAYMENT_METHODS } from "../sales/shared";
import { refreshAfterPayment, todayInput } from "./shared";

/** Register money received from a customer: it settles their oldest open sales first; the rest is credit. */
export function PaymentDialog({
  customer,
  owed,
  onClose,
}: {
  customer: { id: number; name: string };
  /** What the customer owes now, proposed as the amount. */
  owed?: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const formId = useId();
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState(owed && Number(owed) > 0 ? owed.replace(".", ",") : "");
  const [method, setMethod] = useState<SalePaymentMethodEnum>("cash");
  const [receivedOn, setReceivedOn] = useState(todayInput());
  const [reference, setReference] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  const mutation = useMutation({
    mutationFn: () => {
      const value = parseDecimalInput(amount, 3);
      if (value === null || Number(value) <= 0) {
        setErrors({ amount: t("admin.payments.dialog.amountError") });
        return Promise.reject(new Error("invalid"));
      }
      return createCustomerPayment({
        customer: customer.id,
        amount: value,
        method,
        received_on: receivedOn || null,
        reference: reference.trim(),
      });
    },
    onSuccess: async (payment) => {
      toast.success(t("admin.payments.dialog.done", { number: payment.number }));
      await refreshAfterPayment(queryClient);
      onClose();
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      if (Object.keys(fromServer).length > 0) setErrors(fromServer);
      else if (!(failure instanceof Error && failure.message === "invalid"))
        toast.error(t("admin.payments.dialog.error"));
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogTitle>{t("admin.payments.dialog.title", { name: customer.name })}</DialogTitle>
        <DialogDescription>
          {owed !== undefined
            ? t("admin.payments.dialog.bodyOwed", { amount: formatMoney(owed) })
            : t("admin.payments.dialog.body")}
        </DialogDescription>
        <div className="grid grid-cols-2 gap-3 max-[520px]:grid-cols-1">
          <Field label={t("admin.payments.dialog.amount")} htmlFor={`${formId}-amount`} error={errors.amount}>
            <Input
              id={`${formId}-amount`}
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              aria-invalid={errors.amount ? true : undefined}
              autoComplete="off"
            />
          </Field>
          <Field label={t("admin.payments.dialog.method")} htmlFor={`${formId}-method`} error={errors.method}>
            <Select value={method} onValueChange={(value) => setMethod(value as SalePaymentMethodEnum)}>
              <SelectTrigger id={`${formId}-method`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAYMENT_METHODS.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(`admin.sales.methods.${value}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={t("admin.payments.dialog.receivedOn")} htmlFor={`${formId}-day`} error={errors.received_on}>
            <Input
              id={`${formId}-day`}
              type="date"
              value={receivedOn}
              onChange={(event) => setReceivedOn(event.target.value)}
            />
          </Field>
          <Field label={t("admin.payments.dialog.reference")} htmlFor={`${formId}-ref`} error={errors.reference}>
            <Input
              id={`${formId}-ref`}
              value={reference}
              maxLength={50}
              onChange={(event) => setReference(event.target.value)}
              autoComplete="off"
            />
          </Field>
        </div>
        {errors.customer && (
          <p role="alert" className="text-[0.85rem] text-bad">
            {errors.customer}
          </p>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            {t("admin.payments.dialog.cancel")}
          </Button>
          <Button variant="primary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? t("admin.payments.dialog.saving") : t("admin.payments.dialog.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
