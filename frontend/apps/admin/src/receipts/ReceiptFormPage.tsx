import {
  createReceipt,
  type LastCost,
  type ReceiptWrite,
  useListLastPurchaseCosts,
  useListLocations,
  useListProducts,
  useListSuppliers,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatDate, formatMoney, formatPercent, parseDecimalInput, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  CardTitle,
  Field,
  Icon,
  Input,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useMemo, useState } from "react";
import { Navigate, useNavigate, useOutletContext } from "react-router";

import { lineTotal, percentChange, sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { canRecordReceipts, refreshAfterReceipt, todayInTunis } from "./shared";

type LineField = "product" | "ordered_quantity" | "invoiced_quantity" | "accepted_quantity" | "unit_cost" | "use_by";
type Line = Record<LineField, string> & {
  key: number;
  // Once a person types in these, the form stops filling them in.
  acceptedTouched: boolean;
  costTouched: boolean;
};
type Errors = Record<string, string>;

// Gives each line a stable React key, also for lines not saved yet.
let nextKey = 0;
function newLine(): Line {
  nextKey += 1;
  return {
    key: nextKey,
    product: "",
    ordered_quantity: "",
    invoiced_quantity: "",
    accepted_quantity: "",
    unit_cost: "",
    use_by: "",
    acceptedTouched: false,
    costTouched: false,
  };
}

// The API writes "20.250"; people here write "20,250". Both are read back by parseDecimalInput.
const asTyped = (value: string) => value.replace(".", ",");

const lineKey = (index: number, field: string) => `lines.${index}.${field}`;

/** Record goods received from a supplier. Owners and managers only; the server checks it too. */
export function ReceiptFormPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const formId = useId();

  const suppliers = useListSuppliers({ status: "active" });
  const locations = useListLocations({ status: "active" });
  const products = useListProducts({ status: "active" });

  const [supplier, setSupplier] = useState("");
  const [location, setLocation] = useState("");
  const [receivedOn, setReceivedOn] = useState(todayInTunis);
  const [supplierReference, setSupplierReference] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>(() => [newLine()]);
  const [errors, setErrors] = useState<Errors>({});

  const lastCosts = useListLastPurchaseCosts({ supplier: Number(supplier) }, { query: { enabled: supplier !== "" } });
  const lastCostOf = useMemo(() => {
    const byProduct = new Map<string, LastCost>();
    for (const cost of lastCosts.data ?? []) byProduct.set(String(cost.product_id), cost);
    return byProduct;
  }, [lastCosts.data]);

  // Goods usually go to a cold room: the first one is chosen until the person picks another place.
  const firstColdRoom = locations.data?.find((place) => place.kind === "cold_room")?.id;
  const chosenLocation = location || (firstColdRoom !== undefined ? String(firstColdRoom) : "");

  // Until a cost is typed, the line shows the last cost paid to this supplier for the product.
  const costOf = (line: Line): string => {
    if (line.costTouched) return line.unit_cost;
    const last = lastCostOf.get(line.product);
    return last ? asTyped(last.unit_cost) : "";
  };

  const setLine = (key: number, change: (line: Line) => Partial<Line>) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...change(line) } : line)));

  const save = useMutation({
    mutationFn: (payload: ReceiptWrite) => createReceipt(payload),
    onSuccess: async (saved) => {
      toast.success(t("admin.receipts.form.created", { number: saved.number }));
      await refreshAfterReceipt(queryClient);
      void navigate(`/achats/${saved.id}`);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.receipts.form.error") });
    },
  });

  if (!canRecordReceipts(session)) return <Navigate to="/achats" replace />;

  function submit(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!supplier) found.supplier = t("admin.receipts.form.required");
    if (!chosenLocation) found.location = t("admin.receipts.form.required");
    if (!receivedOn) found.received_on = t("admin.receipts.form.required");
    if (lines.length === 0) found.lines = t("admin.receipts.form.noLines");
    const payloadLines: ReceiptWrite["lines"] = [];
    lines.forEach((line, index) => {
      if (!line.product) found[lineKey(index, "product")] = t("admin.receipts.form.required");
      const weight = (field: LineField, optional = false) => {
        const typed = line[field].trim();
        if (optional && typed === "") return null;
        const parsed = parseDecimalInput(typed, 3);
        if (parsed === null || parsed.startsWith("-") || /^0+(\.0+)?$/.test(parsed)) {
          found[lineKey(index, field)] = t("admin.receipts.form.weight");
          return null;
        }
        return parsed;
      };
      const ordered = weight("ordered_quantity", true);
      const invoiced = weight("invoiced_quantity");
      const accepted = weight("accepted_quantity");
      const cost = parseDecimalInput(costOf(line).trim(), 3);
      if (cost === null || cost.startsWith("-")) found[lineKey(index, "unit_cost")] = t("admin.receipts.form.money");
      payloadLines.push({
        product: Number(line.product),
        ordered_quantity: ordered,
        invoiced_quantity: invoiced ?? "",
        accepted_quantity: accepted ?? "",
        unit_cost: cost ?? "",
        use_by: line.use_by || null,
      });
    });
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    save.mutate({
      supplier: Number(supplier),
      location: Number(chosenLocation),
      received_on: receivedOn,
      supplier_reference: supplierReference.trim(),
      notes: notes.trim(),
      lines: payloadLines,
    });
  }

  // Amounts of the lines whose weight and cost are already readable.
  const amounts = lines.map((line) => {
    const invoiced = parseDecimalInput(line.invoiced_quantity.trim(), 3);
    const accepted = parseDecimalInput(line.accepted_quantity.trim(), 3);
    const cost = parseDecimalInput(costOf(line).trim(), 3);
    return {
      invoiced: invoiced && cost ? lineTotal(invoiced, cost) : null,
      accepted: accepted && cost ? lineTotal(accepted, cost) : null,
    };
  });
  const invoicedTotal = sum(amounts.flatMap(({ invoiced }) => (invoiced ? [invoiced] : [])));
  const acceptedTotal = sum(amounts.flatMap(({ accepted }) => (accepted ? [accepted] : [])));

  function lastCostHint(line: Line): string | null {
    if (!supplier || !line.product) return null;
    const last = lastCostOf.get(line.product);
    if (!last) return lastCosts.data ? t("admin.receipts.form.noLastCost") : null;
    const typed = parseDecimalInput(costOf(line).trim(), 3);
    const change = typed && !typed.startsWith("-") ? percentChange(typed, last.unit_cost) : null;
    const values = { cost: formatMoney(last.unit_cost), date: formatDate(last.received_on) };
    return change && change !== "0.0"
      ? t("admin.receipts.form.lastCostChange", { ...values, change: formatPercent(change) })
      : t("admin.receipts.form.lastCost", values);
  }

  const id = (name: string) => `${formId}-${name}`;
  const select = (
    name: string,
    label: string,
    value: string,
    onChange: (value: string) => void,
    options: { value: string; label: string }[],
    className?: string,
  ) => (
    <Field label={label} htmlFor={id(name)} error={errors[name]} className={className}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id(name)} aria-invalid={errors[name] ? true : undefined}>
          <SelectValue placeholder={t("admin.receipts.form.choose")} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );

  return (
    <>
      <PageHeader eyebrow={t("admin.nav.purchases")} title={t("admin.receipts.form.title")} />

      <form id={formId} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card className="grid grid-cols-2 gap-4 max-[640px]:grid-cols-1">
          {select(
            "supplier",
            t("admin.receipts.form.supplier"),
            supplier,
            setSupplier,
            (suppliers.data ?? []).map((one) => ({ value: String(one.id), label: one.name })),
          )}
          {select(
            "location",
            t("admin.receipts.form.location"),
            chosenLocation,
            setLocation,
            (locations.data ?? []).map((place) => ({ value: String(place.id), label: place.name })),
          )}
          <Field label={t("admin.receipts.form.date")} htmlFor={id("received_on")} error={errors.received_on}>
            <Input
              id={id("received_on")}
              type="date"
              max={todayInTunis()}
              value={receivedOn}
              onChange={(event) => setReceivedOn(event.target.value)}
              aria-invalid={errors.received_on ? true : undefined}
            />
          </Field>
          <Field
            label={t("admin.receipts.form.supplierReference")}
            htmlFor={id("supplier_reference")}
            error={errors.supplier_reference}
          >
            <Input
              id={id("supplier_reference")}
              value={supplierReference}
              maxLength={50}
              onChange={(event) => setSupplierReference(event.target.value)}
              autoComplete="off"
            />
          </Field>
        </Card>

        <Card className="flex flex-col gap-3">
          <CardTitle className="mb-0">{t("admin.receipts.form.lines")}</CardTitle>
          <p className="text-[0.85rem] text-ink-2">{t("admin.receipts.form.netWeightHint")}</p>
          {lines.map((line, index) => {
            const hint = lastCostHint(line);
            const amount = amounts[index]?.invoiced;
            const weightInput = (field: LineField, label: string, onChange: (value: string) => void) => (
              <Field label={label} htmlFor={id(lineKey(index, field))} error={errors[lineKey(index, field)]}>
                <Input
                  id={id(lineKey(index, field))}
                  inputMode="decimal"
                  value={field === "unit_cost" ? costOf(line) : line[field]}
                  onChange={(event) => onChange(event.target.value)}
                  aria-invalid={errors[lineKey(index, field)] ? true : undefined}
                  autoComplete="off"
                  className="num"
                />
              </Field>
            );
            return (
              <div
                key={line.key}
                role="group"
                aria-label={t("admin.receipts.form.lineNumber", { number: index + 1 })}
                className="grid grid-cols-[2fr_repeat(4,1fr)_auto] items-start gap-3 rounded-card border border-line p-3 max-[960px]:grid-cols-2"
              >
                {select(
                  lineKey(index, "product"),
                  t("admin.receipts.form.product"),
                  line.product,
                  (value) => setLine(line.key, () => ({ product: value })),
                  (products.data ?? []).map((product) => ({
                    value: String(product.id),
                    label: `${product.name} · ${product.reference}`,
                  })),
                  "max-[960px]:col-span-2",
                )}
                {weightInput("ordered_quantity", t("admin.receipts.form.ordered"), (value) =>
                  setLine(line.key, () => ({ ordered_quantity: value })),
                )}
                {weightInput("invoiced_quantity", t("admin.receipts.form.invoiced"), (value) =>
                  // Most deliveries are accepted as invoiced: the accepted weight follows until it is typed.
                  setLine(line.key, (current) => ({
                    invoiced_quantity: value,
                    ...(current.acceptedTouched ? {} : { accepted_quantity: value }),
                  })),
                )}
                {weightInput("accepted_quantity", t("admin.receipts.form.accepted"), (value) =>
                  setLine(line.key, () => ({ accepted_quantity: value, acceptedTouched: true })),
                )}
                {weightInput("unit_cost", t("admin.receipts.form.cost"), (value) =>
                  setLine(line.key, () => ({ unit_cost: value, costTouched: true })),
                )}
                <div className="flex items-end self-stretch max-[960px]:col-span-2 max-[960px]:justify-end">
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={t("admin.receipts.form.removeLine")}
                    title={t("admin.receipts.form.removeLine")}
                    onClick={() => setLines((current) => current.filter((other) => other.key !== line.key))}
                  >
                    <Icon name="trash" />
                  </Button>
                </div>
                <Field
                  label={t("admin.receipts.form.useBy")}
                  htmlFor={id(lineKey(index, "use_by"))}
                  error={errors[lineKey(index, "use_by")]}
                >
                  <Input
                    id={id(lineKey(index, "use_by"))}
                    type="date"
                    min={receivedOn}
                    value={line.use_by}
                    onChange={(event) => setLine(line.key, () => ({ use_by: event.target.value }))}
                    aria-invalid={errors[lineKey(index, "use_by")] ? true : undefined}
                  />
                </Field>
                <p className="col-span-4 self-end text-[0.85rem] text-ink-2 max-[960px]:col-span-2" aria-live="polite">
                  {hint}
                </p>
                <p className="num self-end text-end font-semibold max-[960px]:col-span-2">
                  {amount ? formatMoney(amount) : ""}
                </p>
              </div>
            );
          })}
          {errors.lines && <p className="text-[0.78rem] font-semibold text-bad">{errors.lines}</p>}
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
            <Button onClick={() => setLines((current) => [...current, newLine()])}>
              <Icon name="plus" />
              {t("admin.receipts.form.addLine")}
            </Button>
            <dl className="ms-auto flex flex-wrap gap-x-8 gap-y-2">
              <div>
                <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.receipts.form.invoicedTotal")}</dt>
                <dd className="num font-bold">{formatMoney(invoicedTotal)}</dd>
              </div>
              <div>
                <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.receipts.form.acceptedTotal")}</dt>
                <dd className="num">{formatMoney(acceptedTotal)}</dd>
              </div>
            </dl>
          </div>
        </Card>

        <Card>
          <Field label={t("admin.receipts.form.notes")} htmlFor={id("notes")} error={errors.notes}>
            <textarea
              id={id("notes")}
              rows={2}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="w-full rounded-control border border-line bg-surface px-3 py-2.5 text-ink"
            />
          </Field>
        </Card>

        {errors.detail && (
          <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
            {errors.detail}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button onClick={() => void navigate("/achats")}>{t("admin.receipts.form.cancel")}</Button>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            {save.isPending ? t("admin.receipts.form.saving") : t("admin.receipts.form.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
