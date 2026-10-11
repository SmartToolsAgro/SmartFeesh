import { allocateSupplierPayment, type SupplierPayment, useListSupplierInvoices } from "@frutti/api";
import { formatMoney, useTranslation } from "@frutti/i18n";
import { Button, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogTitle, toast } from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";

import { sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import {
  type Allocations,
  allocationPayload,
  asTyped,
  byDueDate,
  compare,
  errorsByInvoice,
  hasAllocationProblem,
  spread,
} from "./allocation";
import { AllocationTable } from "./AllocationTable";
import { refreshPurchasing } from "./shared";

/** Allocate the part of a payment not allocated yet (an advance) to the supplier's open invoices. */
export function AllocateDialog({ payment, onDone }: { payment: SupplierPayment; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const formId = useId();
  const open = useListSupplierInvoices({ supplier: payment.supplier.id, status: "open", limit: 200 });
  const invoices = useMemo(() => byDueDate(open.data?.results ?? []), [open.data]);
  const [values, setValues] = useState<Allocations | null>(null);
  const [error, setError] = useState("");
  const [lineErrors, setLineErrors] = useState<Record<number, string>>({});

  // Until the person types, the advance is spread over the oldest due dates first.
  const suggested = useMemo(() => {
    const shares = spread(
      payment.unallocated_amount,
      invoices.map((invoice) => invoice.outstanding),
    );
    return Object.fromEntries(invoices.map((invoice, index) => [invoice.id, asTyped(shares[index] ?? "")]));
  }, [invoices, payment.unallocated_amount]);
  const shown = values ?? suggested;

  const save = useMutation({
    mutationFn: (allocations: { invoice: number; amount: string }[]) =>
      allocateSupplierPayment(payment.id, { allocations }),
    onSuccess: async (saved) => {
      toast.success(t("admin.supplierPayments.allocateDialog.done", { number: saved.number }));
      await refreshPurchasing(queryClient);
      onDone();
    },
    onError: (failure, sent) => {
      const fromServer = fieldErrors(failure);
      setLineErrors(errorsByInvoice(fromServer, sent));
      setError(fromServer.allocations ?? fromServer.detail ?? t("admin.supplierPayments.form.error"));
    },
  });

  function submit() {
    const payload = allocationPayload(invoices, shown);
    if (payload === null || hasAllocationProblem(invoices, shown)) return;
    if (payload.length === 0) {
      setError(t("admin.supplierPayments.allocateDialog.nothing"));
      return;
    }
    const total = sum(payload.map(({ amount }) => amount));
    if (compare(total, payment.unallocated_amount) > 0) {
      setError(t("admin.supplierPayments.form.overAllocated"));
      return;
    }
    setError("");
    save.mutate(payload);
  }

  return (
    <DialogContent className="w-[min(720px,calc(100vw-2rem))]">
      <DialogTitle>{t("admin.supplierPayments.allocateDialog.title", { number: payment.number })}</DialogTitle>
      <DialogDescription>
        {t("admin.supplierPayments.allocateDialog.description", { amount: formatMoney(payment.unallocated_amount) })}
      </DialogDescription>
      {open.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : invoices.length === 0 ? (
        <p className="text-ink-2">{t("admin.supplierPayments.form.noOpenInvoices")}</p>
      ) : (
        <AllocationTable
          idPrefix={formId}
          invoices={invoices}
          values={shown}
          errors={lineErrors}
          onChange={(invoiceId, value) => setValues({ ...shown, [invoiceId]: value })}
        />
      )}
      {error && (
        <p role="alert" className="text-[0.85rem] font-semibold text-bad">
          {error}
        </p>
      )}
      <DialogFooter>
        <DialogClose asChild>
          <Button>{t("admin.supplierPayments.allocateDialog.cancel")}</Button>
        </DialogClose>
        <Button variant="primary" disabled={save.isPending || invoices.length === 0} onClick={submit}>
          {save.isPending
            ? t("admin.supplierPayments.allocateDialog.saving")
            : t("admin.supplierPayments.allocateDialog.save")}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
}
