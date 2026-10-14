import {
  ApiError,
  createQuote,
  type QuoteDetail,
  type QuoteWrite,
  updateQuote,
  useGetQuote,
  useListCustomers,
  useListLocations,
  useListLocationStock,
  useListPriceLists,
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
import { Link, Navigate, useOutletContext, useParams } from "react-router";

import { lineTotal, percentOf, subtract, sum } from "../lib/decimal";
import { useLeave } from "../lib/embedded";
import { fieldErrors } from "../lib/errors";
import { todayInTunis } from "../receipts/shared";
import { canWriteQuotes, refreshAfterQuote } from "./shared";

type Line = {
  key: number;
  product: string;
  quantity: string;
  unit_price: string;
  discount_rate: string;
  // Once a person types a price, the form stops showing the price in force.
  priceTouched: boolean;
};
type Errors = Record<string, string>;

// The server's default validity (D-050); the form shows it so it can be changed before saving.
const VALIDITY_DAYS = 3;
// Radix Select has no empty choice: this value stands for "no location".
const NO_LOCATION = "none";

// Gives each line a stable React key, also for lines not saved yet.
let nextKey = 0;
function newLine(fields: Partial<Line> = {}): Line {
  nextKey += 1;
  return { key: nextKey, product: "", quantity: "", unit_price: "", discount_rate: "", priceTouched: false, ...fields };
}

// The API writes "20.250"; people here write "20,250". Both are read back by parseDecimalInput.
const asTyped = (value: string) => value.replace(".", ",");
const lineKey = (index: number, field: string) => `lines.${index}.${field}`;
// "5.00" is shown as "5", "2.50" as "2,5": a rate is typed like a person writes it.
const rateAsTyped = (value: string) => asTyped(value.replace(/\.?0+$/, ""));

/** An ISO day plus some days, in the calendar (no time zone involved). */
function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** "Nouveau devis": a new draft, or one sent at once. */
export function QuoteFormPage() {
  return <QuoteForm />;
}

/** "Modifier DV-2026-0003": a draft changed, or sent. */
export function QuoteEditPage() {
  const { t } = useTranslation();
  const { quoteId } = useParams();
  const id = Number(quoteId);
  const validId = Number.isInteger(id) && id > 0;
  const quote = useGetQuote(id, { query: { enabled: validId, retry: false } });
  if (validId && quote.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!quote.data) {
    const missing = !validId || (quote.error instanceof ApiError && quote.error.status === 404);
    return (
      <EmptyState illustration="mix" title={missing ? t("admin.quotes.notFound") : t("common.serverUnreachable")} />
    );
  }
  if (quote.data.status !== "draft") return <Navigate to={`/devis/${id}`} replace />;
  return <QuoteForm key={quote.data.id} draft={quote.data} />;
}

function QuoteForm({ draft }: { draft?: QuoteDetail }) {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const { embedded, leave } = useLeave();
  const queryClient = useQueryClient();
  const formId = useId();

  const customers = useListCustomers({ status: "active" });
  const locations = useListLocations({ status: "active" });
  const products = useListProducts({ status: "active" });

  const [customer, setCustomer] = useState(draft ? String(draft.customer.id) : "");
  const [location, setLocation] = useState(draft?.location ? String(draft.location.id) : NO_LOCATION);
  const [day, setDay] = useState(draft?.quoted_on ?? todayInTunis());
  const [validUntil, setValidUntil] = useState(draft?.valid_until ?? addDays(todayInTunis(), VALIDITY_DAYS));
  // Until the validity is typed, it follows the quote's day.
  const [validTouched, setValidTouched] = useState(draft !== undefined);
  const [notes, setNotes] = useState(draft?.notes ?? "");
  const [lines, setLines] = useState<Line[]>(() =>
    draft
      ? draft.lines.map((line) =>
          newLine({
            product: String(line.product.id),
            quantity: asTyped(line.quantity),
            unit_price: asTyped(line.unit_price),
            discount_rate: /^0+(\.0+)?$/.test(line.discount_rate) ? "" : rateAsTyped(line.discount_rate),
            priceTouched: true,
          }),
        )
      : [newLine()],
  );
  const [errors, setErrors] = useState<Errors>({});

  const place = (locations.data ?? []).find((option) => String(option.id) === location);
  const stock = useListLocationStock(Number(location), { query: { enabled: place !== undefined } });
  const availableOf = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const row of stock.data ?? []) byProduct.set(String(row.product_id), row.quantity);
    return byProduct;
  }, [stock.data]);
  const dailyPrice = useMemo(() => {
    const byProduct = new Map<string, string | null>();
    for (const product of products.data ?? []) byProduct.set(String(product.id), product.current_price);
    return byProduct;
  }, [products.data]);
  // The customer's own price list wins over the daily price, as on the server (D-049).
  const priceLists = useListPriceLists(
    { customer: Number(customer), status: "active" },
    { query: { enabled: customer !== "" } },
  );
  const customerList = priceLists.data?.[0];
  const listPrice = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const item of customerList?.items ?? []) byProduct.set(String(item.product), item.price);
    return byProduct;
  }, [customerList]);
  const proposedPrice = (product: string): string | null => listPrice.get(product) ?? dailyPrice.get(product) ?? null;

  // A line shows the price the customer is charged until a price is typed; the server keeps it on the line.
  const priceOf = (line: Line): string => {
    if (line.priceTouched) return line.unit_price;
    const price = proposedPrice(line.product);
    return price ? asTyped(price) : "";
  };

  const setLine = (key: number, change: Partial<Line>) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...change } : line)));

  const save = useMutation({
    mutationFn: (payload: QuoteWrite) => (draft ? updateQuote(draft.id, payload) : createQuote(payload)),
    onSuccess: async (saved) => {
      toast.success(
        t(saved.status === "sent" ? "admin.quotes.form.sent" : "admin.quotes.form.created", { number: saved.number }),
      );
      await refreshAfterQuote(queryClient);
      leave(`/devis/${saved.id}`);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.quotes.form.error") });
    },
  });

  if (!canWriteQuotes(session)) return <Navigate to="/devis" replace />;

  // Browser-side preview of the server's amounts (D-050): gross, discount, net per line.
  const previews = lines.map((line) => {
    const quantity = parseDecimalInput(line.quantity.trim(), 3);
    const price = parseDecimalInput(priceOf(line).trim(), 3);
    const rate = line.discount_rate.trim() === "" ? "0" : parseDecimalInput(line.discount_rate.trim(), 2);
    if (!quantity || !price || !rate || [quantity, price, rate].some((value) => value.startsWith("-"))) return null;
    const gross = lineTotal(quantity, price);
    const discount = percentOf(gross, rate);
    return { gross, discount, amount: subtract(gross, discount) };
  });
  const priced = previews.flatMap((preview) => (preview ? [preview] : []));
  const subtotal = sum(priced.map((preview) => preview.gross));
  const discountTotal = sum(priced.map((preview) => preview.discount));
  const totalExclTax = subtract(subtotal, discountTotal);

  function submit(sendNow: boolean) {
    const found: Errors = {};
    if (!customer) found.customer = t("admin.quotes.form.required");
    if (!day) found.quoted_on = t("admin.quotes.form.required");
    if (!validUntil) found.valid_until = t("admin.quotes.form.required");
    else if (day && validUntil < day) found.valid_until = t("admin.quotes.form.validBefore");
    if (lines.length === 0) found.lines = t("admin.quotes.form.noLines");
    const payloadLines: QuoteWrite["lines"] = [];
    lines.forEach((line, index) => {
      if (!line.product) found[lineKey(index, "product")] = t("admin.quotes.form.required");
      const quantity = parseDecimalInput(line.quantity.trim(), 3);
      if (quantity === null || quantity.startsWith("-") || /^0+(\.0+)?$/.test(quantity)) {
        found[lineKey(index, "quantity")] = t("admin.quotes.form.weight");
      }
      let price: string | null = null;
      const typedPrice = priceOf(line).trim();
      if (typedPrice !== "") {
        price = parseDecimalInput(typedPrice, 3);
        if (price === null || price.startsWith("-")) found[lineKey(index, "unit_price")] = t("admin.quotes.form.money");
      }
      let rate: string | null = null;
      const typedRate = line.discount_rate.trim();
      if (typedRate !== "") {
        rate = parseDecimalInput(typedRate, 2);
        if (rate === null || rate.startsWith("-")) found[lineKey(index, "discount_rate")] = t("admin.quotes.form.rate");
      }
      payloadLines.push({
        product: Number(line.product),
        quantity: quantity ?? "",
        unit_price: price,
        discount_rate: rate,
      });
    });
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    save.mutate({
      customer: Number(customer),
      location: location === NO_LOCATION ? null : Number(location),
      quoted_on: day,
      valid_until: validUntil,
      notes: notes.trim(),
      lines: payloadLines,
      send_now: sendNow,
    });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit(false);
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
          <SelectValue placeholder={t("admin.quotes.form.choose")} />
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
  const dateInput = (name: string, label: string, value: string, onChange: (value: string) => void) => (
    <Field label={label} htmlFor={id(name)} error={errors[name]}>
      <Input
        id={id(name)}
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={errors[name] ? true : undefined}
      />
    </Field>
  );
  const back = draft ? `/devis/${draft.id}` : "/devis";

  return (
    <>
      {!embedded && (
        <Link to={back} className="text-[0.85rem] font-semibold text-sea hover:underline">
          {t("admin.quotes.back")}
        </Link>
      )}
      <PageHeader
        eyebrow={t("admin.quotes.title")}
        title={draft ? t("admin.quotes.form.titleEdit", { number: draft.number }) : t("admin.quotes.form.titleNew")}
      />

      <form id={formId} onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <Card className="grid grid-cols-4 gap-4 max-[1000px]:grid-cols-2 max-[600px]:grid-cols-1">
          {select(
            "customer",
            t("admin.quotes.form.customer"),
            customer,
            setCustomer,
            (customers.data ?? []).map((option) => ({
              value: String(option.id),
              label: `${option.name} · ${option.reference}`,
            })),
            "col-span-2 max-[600px]:col-span-1",
          )}
          {dateInput("quoted_on", t("admin.quotes.form.date"), day, (value) => {
            setDay(value);
            if (!validTouched && value) setValidUntil(addDays(value, VALIDITY_DAYS));
          })}
          {dateInput("valid_until", t("admin.quotes.form.validUntil"), validUntil, (value) => {
            setValidUntil(value);
            setValidTouched(true);
          })}
          <div className="col-span-2 max-[600px]:col-span-1">
            {select("location", t("admin.quotes.form.location"), location, setLocation, [
              { value: NO_LOCATION, label: t("admin.quotes.form.noLocation") },
              ...(locations.data ?? []).map((option) => ({ value: String(option.id), label: option.name })),
            ])}
          </div>
          <p className="col-span-2 self-end pb-2.5 text-[0.85rem] text-ink-2 max-[600px]:col-span-1">
            {t("admin.quotes.form.locationHint")}
          </p>
        </Card>

        <Card className="flex flex-col gap-3">
          <CardTitle className="mb-0">{t("admin.quotes.form.lines")}</CardTitle>
          {lines.map((line, index) => {
            const available = line.product ? availableOf.get(line.product) : undefined;
            const fromList = line.product ? listPrice.get(line.product) : undefined;
            const inForce = line.product ? dailyPrice.get(line.product) : undefined;
            const hints = [
              line.product
                ? fromList && customerList
                  ? t("admin.quotes.form.listPrice", { list: customerList.name, price: formatMoney(fromList) })
                  : inForce
                    ? t("admin.quotes.form.priceInForce", { price: formatMoney(inForce) })
                    : t("admin.quotes.form.noPrice")
                : null,
              line.product && place && stock.data
                ? available
                  ? t("admin.quotes.form.available", { location: place.name, quantity: formatQuantity(available) })
                  : t("admin.quotes.form.notAvailable", { location: place.name })
                : null,
            ].filter(Boolean);
            const preview = previews[index];
            const input = (field: "quantity" | "unit_price" | "discount_rate", label: string) => (
              <Field label={label} htmlFor={id(lineKey(index, field))} error={errors[lineKey(index, field)]}>
                <Input
                  id={id(lineKey(index, field))}
                  inputMode="decimal"
                  value={field === "unit_price" ? priceOf(line) : line[field]}
                  onChange={(event) =>
                    setLine(
                      line.key,
                      field === "unit_price"
                        ? { unit_price: event.target.value, priceTouched: true }
                        : { [field]: event.target.value },
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
                aria-label={t("admin.quotes.form.lineNumber", { number: index + 1 })}
                className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] items-start gap-3 rounded-card border border-line p-3 max-[900px]:grid-cols-3"
              >
                {select(
                  lineKey(index, "product"),
                  t("admin.quotes.form.product"),
                  line.product,
                  (value) => setLine(line.key, { product: value, priceTouched: false, unit_price: "" }),
                  (products.data ?? []).map((product) => ({
                    value: String(product.id),
                    label: `${product.name} · ${product.reference}`,
                  })),
                  "max-[900px]:col-span-3",
                )}
                {input("quantity", t("admin.quotes.form.quantity"))}
                {input("unit_price", t("admin.quotes.form.price"))}
                {input("discount_rate", t("admin.quotes.form.discount"))}
                <div className="flex items-end self-stretch max-[900px]:col-span-3 max-[900px]:justify-end">
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={t("admin.quotes.form.removeLine")}
                    title={t("admin.quotes.form.removeLine")}
                    onClick={() => setLines((current) => current.filter((other) => other.key !== line.key))}
                  >
                    <Icon name="trash" />
                  </Button>
                </div>
                <p className="col-span-4 text-[0.85rem] text-ink-2 max-[900px]:col-span-2" aria-live="polite">
                  {hints.join(" · ")}
                </p>
                <p className="num text-end font-semibold">{preview ? formatMoney(preview.amount) : ""}</p>
              </div>
            );
          })}
          {errors.lines && <p className="text-[0.78rem] font-semibold text-bad">{errors.lines}</p>}
          <div className="flex flex-wrap items-start gap-x-8 gap-y-2">
            <Button onClick={() => setLines((current) => [...current, newLine()])}>
              <Icon name="plus" />
              {t("admin.quotes.form.addLine")}
            </Button>
            <dl className="ms-auto flex flex-wrap gap-x-8 gap-y-2">
              {discountTotal !== "0.000" && (
                <>
                  <div>
                    <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.quotes.detail.subtotal")}</dt>
                    <dd className="num">{formatMoney(subtotal)}</dd>
                  </div>
                  <div>
                    <dt className="text-[0.78rem] font-semibold text-ink-2">
                      {t("admin.quotes.detail.discountTotal")}
                    </dt>
                    <dd className="num">−{formatMoney(discountTotal)}</dd>
                  </div>
                </>
              )}
              <div>
                <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.quotes.detail.totalExclTax")}</dt>
                <dd className="num font-bold">{formatMoney(totalExclTax)}</dd>
              </div>
            </dl>
          </div>
        </Card>

        <Card>
          <Field label={t("admin.quotes.form.notes")} htmlFor={id("notes")} error={errors.notes}>
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
          <Button onClick={() => leave(back)}>{t("admin.quotes.form.cancel")}</Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? t("admin.quotes.form.saving") : t("admin.quotes.form.saveDraft")}
          </Button>
          <Button variant="primary" disabled={save.isPending} onClick={() => submit(true)}>
            <Icon name="check" />
            {t("admin.quotes.form.send")}
          </Button>
        </div>
      </form>
    </>
  );
}
