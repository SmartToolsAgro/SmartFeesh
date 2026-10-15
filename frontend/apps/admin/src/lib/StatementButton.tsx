import { getGetCustomerStatementPdfUrl, getGetSupplierStatementPdfUrl } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import {
  Button,
  cn,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  Field,
  Icon,
  Input,
  toast,
} from "@frutti/ui";
import { type FormEvent, useId, useState } from "react";

import { todayInTunis } from "../receipts/shared";

type Mode = "until" | "between";

/** Opens the PDF made on the spot by the server in a new tab (the tab is opened at the click, so it is not blocked). */
async function openStatement(url: string): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) throw new Error(`status ${response.status}`);
    const address = URL.createObjectURL(await response.blob());
    if (tab) tab.location.href = address;
    else window.location.href = address;
    // Kept for a minute: the tab needs the address to load it.
    setTimeout(() => URL.revokeObjectURL(address), 60_000);
  } catch (error) {
    tab?.close();
    throw error;
  }
}

/** "Relevé (PDF)": the statement of a customer or a supplier up to a day or between two days (D-156). */
export function StatementButton({ side, id, name }: { side: "customer" | "supplier"; id: number; name: string }) {
  const { t } = useTranslation();
  const formId = useId();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("until");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState(todayInTunis);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const from = mode === "between" ? dateFrom : "";
    if (!dateTo || (mode === "between" && !from)) {
      setError(t("admin.partyStatement.required"));
      return;
    }
    if (from && from > dateTo) {
      setError(t("admin.partyStatement.order"));
      return;
    }
    setError("");
    const params = { date_to: dateTo, ...(from ? { date_from: from } : {}) };
    const url =
      side === "customer" ? getGetCustomerStatementPdfUrl(id, params) : getGetSupplierStatementPdfUrl(id, params);
    setBusy(true);
    try {
      await openStatement(url);
      setOpen(false);
    } catch {
      toast.error(t("admin.partyStatement.failed"));
    } finally {
      setBusy(false);
    }
  };

  const segment = (value: Mode, label: string) => (
    <button
      type="button"
      aria-pressed={mode === value}
      onClick={() => setMode(value)}
      className={cn(
        "rounded-[7px] px-3 py-1.5 text-[0.85rem] font-semibold text-ink-2",
        mode === value && "bg-surface text-ink shadow-card",
      )}
    >
      {label}
    </button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="ghost" onClick={() => setOpen(true)}>
        <Icon name="receipt" />
        {t("admin.partyStatement.button")}
      </Button>
      {open && (
        <DialogContent className="w-[min(520px,calc(100vw-2rem))]">
          <DialogTitle>{t("admin.partyStatement.title", { name })}</DialogTitle>
          <DialogDescription>{t("admin.partyStatement.description")}</DialogDescription>
          <form id={formId} onSubmit={(event) => void submit(event)} noValidate className="flex flex-col gap-4">
            <div
              role="group"
              aria-label={t("admin.partyStatement.mode")}
              className="flex self-start rounded-control bg-surface-2 p-1"
            >
              {segment("until", t("admin.partyStatement.untilDay"))}
              {segment("between", t("admin.partyStatement.between"))}
            </div>
            <div className="grid grid-cols-2 gap-4 max-[480px]:grid-cols-1">
              {mode === "between" && (
                <Field label={t("admin.partyStatement.dateFrom")} htmlFor={`${formId}-from`}>
                  <Input
                    id={`${formId}-from`}
                    type="date"
                    value={dateFrom}
                    max={dateTo || undefined}
                    onChange={(event) => setDateFrom(event.target.value)}
                  />
                </Field>
              )}
              <Field
                label={t(mode === "between" ? "admin.partyStatement.dateTo" : "admin.partyStatement.until")}
                htmlFor={`${formId}-to`}
              >
                <Input
                  id={`${formId}-to`}
                  type="date"
                  value={dateTo}
                  onChange={(event) => setDateTo(event.target.value)}
                />
              </Field>
            </div>
            {error && (
              <p role="alert" className="text-[0.78rem] font-semibold text-bad">
                {error}
              </p>
            )}
          </form>
          <DialogFooter>
            <Button onClick={() => setOpen(false)}>{t("admin.partyStatement.cancel")}</Button>
            <Button type="submit" form={formId} variant="primary" disabled={busy}>
              {busy ? t("admin.partyStatement.making") : t("admin.partyStatement.open")}
            </Button>
          </DialogFooter>
        </DialogContent>
      )}
    </Dialog>
  );
}
