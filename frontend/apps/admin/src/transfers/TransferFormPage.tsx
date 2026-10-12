import {
  ApiError,
  createTransfer,
  type StockLocation,
  type TransferDetail,
  type TransferKindEnum,
  type TransferWrite,
  updateTransfer,
  useGetTransfer,
  useListLocations,
  useListLocationStock,
  useListProducts,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  CardTitle,
  EmptyState,
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
import { Link, Navigate, useNavigate, useOutletContext, useParams } from "react-router";

import { lineTotal, sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { todayInTunis } from "../receipts/shared";
import { canRecordTransfers, refreshAfterTransfer } from "./shared";

type Line = {
  key: number;
  product: string;
  quantity: string;
  unit_price: string;
  // Once a person types a price, the form stops showing the price in force.
  priceTouched: boolean;
};
type Errors = Record<string, string>;

// Gives each line a stable React key, also for lines not saved yet.
let nextKey = 0;
function newLine(fields: Partial<Line> = {}): Line {
  nextKey += 1;
  return { key: nextKey, product: "", quantity: "", unit_price: "", priceTouched: false, ...fields };
}

// The API writes "20.250"; people here write "20,250". Both are read back by parseDecimalInput.
const asTyped = (value: string) => value.replace(".", ",");
const lineKey = (index: number, field: string) => `lines.${index}.${field}`;

/** Into a truck is a load, out of one a return: the server decides the same way. */
function kindOf(from: StockLocation | undefined, to: StockLocation | undefined): TransferKindEnum | null {
  if (!from || !to) return null;
  const fromTruck = from.kind === "truck";
  const toTruck = to.kind === "truck";
  if (toTruck && !fromTruck) return "load";
  if (fromTruck && !toTruck) return "return";
  return "internal";
}

/** "Nouveau transfert": a new draft, or one validated at once. */
export function TransferFormPage() {
  return <TransferForm />;
}

/** "Modifier TR-0003": a draft changed, or validated. */
export function TransferEditPage() {
  const { t } = useTranslation();
  const { transferId } = useParams();
  const id = Number(transferId);
  const validId = Number.isInteger(id) && id > 0;
  const transfer = useGetTransfer(id, { query: { enabled: validId, retry: false } });
  if (validId && transfer.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!transfer.data) {
    const missing = !validId || (transfer.error instanceof ApiError && transfer.error.status === 404);
    return (
      <EmptyState
        illustration="truck"
        title={missing ? t("admin.transfers.notFound") : t("common.serverUnreachable")}
      />
    );
  }
  if (transfer.data.status !== "draft") return <Navigate to={`/stock/transferts/${id}`} replace />;
  return <TransferForm key={transfer.data.id} draft={transfer.data} />;
}

function TransferForm({ draft }: { draft?: TransferDetail }) {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const formId = useId();

  // Archived places too: a draft may name one archived since (it shows, and the server refuses it on save).
  const locations = useListLocations({ status: "all" });
  const products = useListProducts({ status: "active" });

  const [from, setFrom] = useState(draft ? String(draft.from_location.id) : "");
  const [to, setTo] = useState(draft ? String(draft.to_location.id) : "");
  const [day, setDay] = useState(draft?.transferred_on ?? todayInTunis());
  const [notes, setNotes] = useState(draft?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() =>
    draft
      ? draft.lines.map((line) =>
          newLine({
            product: String(line.product.id),
            quantity: asTyped(line.quantity),
            unit_price: line.unit_price ? asTyped(line.unit_price) : "",
            priceTouched: line.unit_price !== null,
          }),
        )
      : [newLine()],
  );
  const [errors, setErrors] = useState<Errors>({});

  const places = locations.data ?? [];
  const fromPlace = places.find((place) => String(place.id) === from);
  const toPlace = places.find((place) => String(place.id) === to);
  const kind = kindOf(fromPlace, toPlace);

  const stock = useListLocationStock(Number(from), { query: { enabled: from !== "" } });
  const availableOf = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const row of stock.data ?? []) byProduct.set(String(row.product_id), row.quantity);
    return byProduct;
  }, [stock.data]);
  const priceInForce = useMemo(() => {
    const byProduct = new Map<string, string | null>();
    for (const product of products.data ?? []) byProduct.set(String(product.id), product.current_price);
    return byProduct;
  }, [products.data]);

  // A load line shows the price in force until a price is typed.
  const priceOf = (line: Line): string => {
    if (line.priceTouched) return line.unit_price;
    const price = priceInForce.get(line.product);
    return price ? asTyped(price) : "";
  };

  const setLine = (key: number, change: Partial<Line>) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...change } : line)));

  const save = useMutation({
    mutationFn: (payload: TransferWrite) => (draft ? updateTransfer(draft.id, payload) : createTransfer(payload)),
    onSuccess: async (saved) => {
      toast.success(
        t(saved.status === "validated" ? "admin.transfers.form.validated" : "admin.transfers.form.created", {
          number: saved.number,
        }),
      );
      await refreshAfterTransfer(queryClient);
      void navigate(`/stock/transferts/${saved.id}`);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.transfers.form.error") });
    },
  });

  if (!canRecordTransfers(session)) return <Navigate to="/stock/transferts" replace />;

  function submit(validateNow: boolean) {
    const found: Errors = {};
    if (!from) found.from_location = t("admin.transfers.form.required");
    if (!to) found.to_location = t("admin.transfers.form.required");
    if (from && from === to) found.to_location = t("admin.transfers.form.samePlace");
    if (!day) found.transferred_on = t("admin.transfers.form.required");
    if (lines.length === 0) found.lines = t("admin.transfers.form.noLines");
    const payloadLines: TransferWrite["lines"] = [];
    lines.forEach((line, index) => {
      if (!line.product) found[lineKey(index, "product")] = t("admin.transfers.form.required");
      const quantity = parseDecimalInput(line.quantity.trim(), 3);
      if (quantity === null || quantity.startsWith("-") || /^0+(\.0+)?$/.test(quantity)) {
        found[lineKey(index, "quantity")] = t("admin.transfers.form.weight");
      }
      let price: string | null = null;
      if (kind === "load") {
        const typed = priceOf(line).trim();
        if (typed !== "") {
          price = parseDecimalInput(typed, 3);
          if (price === null || price.startsWith("-"))
            found[lineKey(index, "unit_price")] = t("admin.transfers.form.money");
        }
      }
      payloadLines.push({ product: Number(line.product), quantity: quantity ?? "", unit_price: price });
    });
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    save.mutate({
      from_location: Number(from),
      to_location: Number(to),
      transferred_on: day,
      notes: notes.trim(),
      lines: payloadLines,
      validate_now: validateNow,
    });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit(false);
  }

  function takeAll() {
    const rows = stock.data ?? [];
    setLines(rows.map((row) => newLine({ product: String(row.product_id), quantity: asTyped(row.quantity) })));
  }

  const amounts = lines.map((line) => {
    if (kind !== "load") return null;
    const quantity = parseDecimalInput(line.quantity.trim(), 3);
    const price = parseDecimalInput(priceOf(line).trim(), 3);
    return quantity && price && !quantity.startsWith("-") && !price.startsWith("-") ? lineTotal(quantity, price) : null;
  });
  const total = sum(amounts.flatMap((amount) => (amount ? [amount] : [])));

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
          <SelectValue placeholder={t("admin.transfers.form.choose")} />
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
  const placeOptions = places
    .filter((place) => place.is_active || String(place.id) === from || String(place.id) === to)
    .map((place) => ({ value: String(place.id), label: place.is_active ? place.name : t("admin.transfers.form.archivedPlace", { name: place.name }),
    }));
  const back = draft ? `/stock/transferts/${draft.id}` : "/stock/transferts";

  return (
    <>
      <Link to={back} className="text-[0.85rem] font-semibold text-sea hover:underline">
        {t("admin.transfers.back")}
      </Link>
      <PageHeader
        eyebrow={t("admin.transfers.title")}
        title={
          draft ? t("admin.transfers.form.titleEdit", { number: draft.number }) : t("admin.transfers.form.titleNew")
        }
      />

      <form id={formId} onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <Card className="grid grid-cols-3 gap-4 max-[800px]:grid-cols-1">
          {select("from_location", t("admin.transfers.form.from"), from, setFrom, placeOptions)}
          {select("to_location", t("admin.transfers.form.to"), to, setTo, placeOptions)}
          <Field label={t("admin.transfers.form.date")} htmlFor={id("transferred_on")} error={errors.transferred_on}>
            <Input
              id={id("transferred_on")}
              type="date"
              value={day}
              onChange={(event) => setDay(event.target.value)}
              aria-invalid={errors.transferred_on ? true : undefined}
            />
          </Field>
          {kind && (
            <p className="col-span-full flex items-center gap-2 text-[0.88rem] text-ink-2" aria-live="polite">
              <Icon name={kind === "load" ? "truck" : kind === "return" ? "return" : "snow"} />
              {t(`admin.transfers.form.kindHint.${kind}`)}
            </p>
          )}
        </Card>

        <Card className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <CardTitle className="mb-0">{t("admin.transfers.form.lines")}</CardTitle>
            {/* Emptying a truck in the evening: everything it holds comes back. */}
            {fromPlace?.kind === "truck" && (stock.data?.length ?? 0) > 0 && (
              <Button className="ms-auto" title={t("admin.transfers.form.takeAllHint")} onClick={takeAll}>
                <Icon name="return" />
                {t("admin.transfers.form.takeAll")}
              </Button>
            )}
          </div>
          {lines.map((line, index) => {
            const available = line.product ? availableOf.get(line.product) : undefined;
            const inForce = line.product ? priceInForce.get(line.product) : undefined;
            const hints = [
              line.product && from && stock.data
                ? available
                  ? t("admin.transfers.form.available", { quantity: formatQuantity(available) })
                  : t("admin.transfers.form.notAvailable")
                : null,
              kind === "load" && line.product
                ? inForce
                  ? t("admin.transfers.form.priceInForce", { price: formatMoney(inForce) })
                  : t("admin.transfers.form.noPrice")
                : null,
            ].filter(Boolean);
            const amount = amounts[index];
            const input = (field: "quantity" | "unit_price", label: string) => (
              <Field label={label} htmlFor={id(lineKey(index, field))} error={errors[lineKey(index, field)]}>
                <Input
                  id={id(lineKey(index, field))}
                  inputMode="decimal"
                  value={field === "unit_price" ? priceOf(line) : line.quantity}
                  onChange={(event) =>
                    setLine(
                      line.key,
                      field === "unit_price"
                        ? { unit_price: event.target.value, priceTouched: true }
                        : { quantity: event.target.value },
                    )
                  }
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
                aria-label={t("admin.transfers.form.lineNumber", { number: index + 1 })}
                className="grid grid-cols-[2fr_1fr_1fr_auto] items-start gap-3 rounded-card border border-line p-3 max-[800px]:grid-cols-2"
              >
                {select(
                  lineKey(index, "product"),
                  t("admin.transfers.form.product"),
                  line.product,
                  (value) => setLine(line.key, { product: value }),
                  (products.data ?? []).map((product) => ({
                    value: String(product.id),
                    label: `${product.name} · ${product.reference}`,
                  })),
                  "max-[800px]:col-span-2",
                )}
                {input("quantity", t("admin.transfers.form.quantity"))}
                {kind === "load" ? input("unit_price", t("admin.transfers.form.price")) : <div />}
                <div className="flex items-end self-stretch max-[800px]:col-span-2 max-[800px]:justify-end">
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={t("admin.transfers.form.removeLine")}
                    title={t("admin.transfers.form.removeLine")}
                    onClick={() => setLines((current) => current.filter((other) => other.key !== line.key))}
                  >
                    <Icon name="trash" />
                  </Button>
                </div>
                <p className="col-span-3 text-[0.85rem] text-ink-2 max-[800px]:col-span-2" aria-live="polite">
                  {hints.join(" · ")}
                </p>
                <p className="num text-end font-semibold max-[800px]:col-span-2">{amount ? formatMoney(amount) : ""}</p>
              </div>
            );
          })}
          {errors.lines && <p className="text-[0.78rem] font-semibold text-bad">{errors.lines}</p>}
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
            <Button onClick={() => setLines((current) => [...current, newLine()])}>
              <Icon name="plus" />
              {t("admin.transfers.form.addLine")}
            </Button>
            {kind === "load" && (
              <dl className="ms-auto">
                <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.transfers.detail.totalAmount")}</dt>
                <dd className="num font-bold">{formatMoney(total)}</dd>
              </dl>
            )}
          </div>
        </Card>

        <Card>
          <Field label={t("admin.transfers.form.notes")} htmlFor={id("notes")} error={errors.notes}>
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

        <div className="flex flex-wrap justify-end gap-2">
          <Button onClick={() => void navigate(back)}>{t("admin.transfers.form.cancel")}</Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? t("admin.transfers.form.saving") : t("admin.transfers.form.saveDraft")}
          </Button>
          <Button variant="primary" disabled={save.isPending} onClick={() => submit(true)}>
            <Icon name="check" />
            {t("admin.transfers.form.validate")}
          </Button>
        </div>
      </form>
    </>
  );
}
