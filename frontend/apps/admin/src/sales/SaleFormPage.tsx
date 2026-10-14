import {
  ApiError,
  createSale,
  type SaleDetail,
  type SalePaymentMethodEnum,
  type SaleWrite,
  updateSale,
  useGetSale,
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
import { canSell, localInputOf, momentOf, PAYMENT_METHODS, refreshAfterSale } from "./shared";

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

// Radix Select has no empty choice: these values stand for "the walk-in customer" and "not paid".
const WALK_IN = "walk-in";
const NO_METHOD = "none";

let nextKey = 0;
function newLine(fields: Partial<Line> = {}): Line {
  nextKey += 1;
  return { key: nextKey, product: "", quantity: "", unit_price: "", discount_rate: "", priceTouched: false, ...fields };
}

// The API writes "20.250"; people here write "20,250". Both are read back by parseDecimalInput.
const asTyped = (value: string) => value.replace(".", ",");
const lineKey = (index: number, field: string) => `lines.${index}.${field}`;
const rateAsTyped = (value: string) => asTyped(value.replace(/\.?0+$/, ""));
const isZero = (value: string) => /^0+(\.0+)?$/.test(value);

/** "Nouvelle vente": a draft, or a sale confirmed at once. */
export function SaleFormPage() {
  return <SaleForm />;
}

/** "Modifier VE-0003": a draft changed, or confirmed. */
export function SaleEditPage() {
  const { t } = useTranslation();
  const { saleId } = useParams();
  const id = Number(saleId);
  const validId = Number.isInteger(id) && id > 0;
  const sale = useGetSale(id, { query: { enabled: validId, retry: false } });
  if (validId && sale.isPending) return <p className="text-ink-2">{t("common.loading")}</p>;
  if (!sale.data) {
    const missing = !validId || (sale.error instanceof ApiError && sale.error.status === 404);
    return (
      <EmptyState illustration="mix" title={missing ? t("admin.sales.notFound") : t("common.serverUnreachable")} />
    );
  }
  if (sale.data.status !== "draft") return <Navigate to={`/ventes/${id}`} replace />;
  return <SaleForm key={sale.data.id} draft={sale.data} />;
}

function SaleForm({ draft }: { draft?: SaleDetail }) {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const { embedded, leave } = useLeave();
  const queryClient = useQueryClient();
  const formId = useId();

  const customers = useListCustomers({ status: "active" });
  const locations = useListLocations({ status: "active" });
  const products = useListProducts({ status: "active" });

  const [customer, setCustomer] = useState(
    draft && !draft.customer.is_walk_in ? String(draft.customer.id) : draft ? WALK_IN : "",
  );
  const [location, setLocation] = useState(draft ? String(draft.location.id) : "");
  const [soldAt, setSoldAt] = useState(draft ? localInputOf(draft.sold_at) : "");
  const [notes, setNotes] = useState(draft?.notes ?? "");
  const [paidInFull, setPaidInFull] = useState(false);
  const [amountPaid, setAmountPaid] = useState(draft && !isZero(draft.amount_paid) ? asTyped(draft.amount_paid) : "");
  const [method, setMethod] = useState<string>(draft?.payment_method || NO_METHOD);
  const [reference, setReference] = useState(draft?.payment_reference ?? "");
  const [lines, setLines] = useState<Line[]>(() =>
    draft
      ? draft.lines.map((line) =>
          newLine({
            product: String(line.product.id),
            quantity: asTyped(line.quantity),
            unit_price: asTyped(line.unit_price),
            discount_rate: isZero(line.discount_rate) ? "" : rateAsTyped(line.discount_rate),
            priceTouched: true,
          }),
        )
      : [newLine()],
  );
  const [errors, setErrors] = useState<Errors>({});

  const places = (locations.data ?? []).filter((option) => option.sells);
  const place = places.find((option) => String(option.id) === location);
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
  const realCustomer = customer !== "" && customer !== WALK_IN;
  const priceLists = useListPriceLists(
    { customer: Number(customer), status: "active" },
    { query: { enabled: realCustomer } },
  );
  const customerList = realCustomer ? priceLists.data?.[0] : undefined;
  const listPrice = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const item of customerList?.items ?? []) byProduct.set(String(item.product), item.price);
    return byProduct;
  }, [customerList]);
  const proposedPrice = (product: string): string | null => listPrice.get(product) ?? dailyPrice.get(product) ?? null;
  const priceOf = (line: Line): string => {
    if (line.priceTouched) return line.unit_price;
    const price = proposedPrice(line.product);
    return price ? asTyped(price) : "";
  };

  const setLine = (key: number, change: Partial<Line>) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...change } : line)));

  const save = useMutation({
    mutationFn: (payload: SaleWrite) => (draft ? updateSale(draft.id, payload) : createSale(payload)),
    onSuccess: async (saved) => {
      toast.success(
        t(saved.status === "confirmed" ? "admin.sales.form.confirmed" : "admin.sales.form.created", {
          number: saved.number,
        }),
      );
      await refreshAfterSale(queryClient);
      leave(`/ventes/${saved.id}`);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.sales.form.error") });
    },
  });

  if (!canSell(session)) return <Navigate to="/ventes" replace />;

  // Browser-side preview of the server's amounts: gross, discount, net per line.
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

  function submit(confirmNow: boolean) {
    const found: Errors = {};
    if (!customer) found.customer = t("admin.sales.form.required");
    if (!location) found.location = t("admin.sales.form.required");
    if (lines.length === 0) found.lines = t("admin.sales.form.noLines");
    const payloadLines: SaleWrite["lines"] = [];
    lines.forEach((line, index) => {
      if (!line.product) found[lineKey(index, "product")] = t("admin.sales.form.required");
      const quantity = parseDecimalInput(line.quantity.trim(), 3);
      if (quantity === null || quantity.startsWith("-") || isZero(quantity)) {
        found[lineKey(index, "quantity")] = t("admin.sales.form.weight");
      }
      let price: string | null = null;
      const typedPrice = priceOf(line).trim();
      if (typedPrice !== "") {
        price = parseDecimalInput(typedPrice, 3);
        if (price === null || price.startsWith("-")) found[lineKey(index, "unit_price")] = t("admin.sales.form.money");
      }
      let rate: string | null = null;
      const typedRate = line.discount_rate.trim();
      if (typedRate !== "") {
        rate = parseDecimalInput(typedRate, 2);
        if (rate === null || rate.startsWith("-")) found[lineKey(index, "discount_rate")] = t("admin.sales.form.rate");
      }
      payloadLines.push({
        product: Number(line.product),
        quantity: quantity ?? "",
        unit_price: price,
        discount_rate: rate,
      });
    });
    let paid: string | null = null;
    if (!paidInFull && amountPaid.trim() !== "") {
      paid = parseDecimalInput(amountPaid.trim(), 3);
      if (paid === null || paid.startsWith("-")) found.amount_paid = t("admin.sales.form.money");
    }
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    save.mutate({
      customer: customer === WALK_IN ? null : Number(customer),
      location: Number(location),
      sold_at: momentOf(soldAt),
      notes: notes.trim(),
      lines: payloadLines,
      paid_in_full: paidInFull,
      amount_paid: paid,
      payment_method: method === NO_METHOD ? "" : (method as SalePaymentMethodEnum),
      payment_reference: reference.trim(),
      confirm_now: confirmNow,
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
          <SelectValue placeholder={t("admin.sales.form.choose")} />
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
  const back = draft ? `/ventes/${draft.id}` : "/ventes";

  return (
    <>
      {!embedded && (
        <Link to={back} className="text-[0.85rem] font-semibold text-sea hover:underline">
          {t("admin.sales.back")}
        </Link>
      )}
      <PageHeader
        eyebrow={t("admin.sales.title")}
        title={draft ? t("admin.sales.form.titleEdit", { number: draft.number }) : t("admin.sales.form.titleNew")}
      />

      <form id={formId} onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <Card className="grid grid-cols-4 gap-4 max-[1000px]:grid-cols-2 max-[600px]:grid-cols-1">
          {select(
            "customer",
            t("admin.sales.form.customer"),
            customer,
            setCustomer,
            [
              { value: WALK_IN, label: t("admin.sales.form.walkIn") },
              ...(customers.data ?? [])
                .filter((option) => !option.is_walk_in)
                .map((option) => ({ value: String(option.id), label: `${option.name} · ${option.reference}` })),
            ],
            "col-span-2 max-[600px]:col-span-1",
          )}
          {select(
            "location",
            t("admin.sales.form.location"),
            location,
            setLocation,
            places.map((option) => ({ value: String(option.id), label: option.name })),
          )}
          <Field label={t("admin.sales.form.soldAt")} htmlFor={id("sold_at")} error={errors.sold_at}>
            <Input
              id={id("sold_at")}
              type="datetime-local"
              value={soldAt}
              onChange={(event) => setSoldAt(event.target.value)}
              aria-invalid={errors.sold_at ? true : undefined}
              aria-describedby={id("sold_at_hint")}
            />
            <p id={id("sold_at_hint")} className="text-[0.8rem] text-ink-2">
              {t("admin.sales.form.soldAtHint")}
            </p>
          </Field>
          <p className="col-span-4 text-[0.85rem] text-ink-2 max-[1000px]:col-span-2 max-[600px]:col-span-1">
            {t("admin.sales.form.locationHint")}
          </p>
        </Card>

        <Card className="flex flex-col gap-3">
          <CardTitle className="mb-0">{t("admin.sales.form.lines")}</CardTitle>
          {lines.map((line, index) => {
            const available = line.product ? availableOf.get(line.product) : undefined;
            const fromList = line.product ? listPrice.get(line.product) : undefined;
            const inForce = line.product ? dailyPrice.get(line.product) : undefined;
            const hints = [
              line.product
                ? fromList && customerList
                  ? t("admin.sales.form.listPrice", { list: customerList.name, price: formatMoney(fromList) })
                  : inForce
                    ? t("admin.sales.form.priceInForce", { price: formatMoney(inForce) })
                    : t("admin.sales.form.noPrice")
                : null,
              line.product && place && stock.data
                ? available
                  ? t("admin.sales.form.available", { location: place.name, quantity: formatQuantity(available) })
                  : t("admin.sales.form.notAvailable", { location: place.name })
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
                aria-label={t("admin.sales.form.lineNumber", { number: index + 1 })}
                className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] items-start gap-3 rounded-card border border-line p-3 max-[900px]:grid-cols-3"
              >
                {select(
                  lineKey(index, "product"),
                  t("admin.sales.form.product"),
                  line.product,
                  (value) => setLine(line.key, { product: value, priceTouched: false, unit_price: "" }),
                  (products.data ?? []).map((product) => ({
                    value: String(product.id),
                    label: `${product.name} · ${product.reference}`,
                  })),
                  "max-[900px]:col-span-3",
                )}
                {input("quantity", t("admin.sales.form.quantity"))}
                {input("unit_price", t("admin.sales.form.price"))}
                {input("discount_rate", t("admin.sales.form.discount"))}
                <div className="flex items-end self-stretch max-[900px]:col-span-3 max-[900px]:justify-end">
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={t("admin.sales.form.removeLine")}
                    title={t("admin.sales.form.removeLine")}
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
              {t("admin.sales.form.addLine")}
            </Button>
            <dl className="ms-auto flex flex-wrap gap-x-8 gap-y-2">
              {discountTotal !== "0.000" && (
                <>
                  <div>
                    <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.sales.detail.subtotal")}</dt>
                    <dd className="num">{formatMoney(subtotal)}</dd>
                  </div>
                  <div>
                    <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.sales.detail.discountTotal")}</dt>
                    <dd className="num">−{formatMoney(discountTotal)}</dd>
                  </div>
                </>
              )}
              <div>
                <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.sales.detail.totalExclTax")}</dt>
                <dd className="num font-bold">{formatMoney(totalExclTax)}</dd>
              </div>
            </dl>
          </div>
        </Card>

        <Card className="grid grid-cols-4 items-start gap-4 max-[1000px]:grid-cols-2 max-[600px]:grid-cols-1">
          <CardTitle className="col-span-4 mb-0 max-[1000px]:col-span-2 max-[600px]:col-span-1">
            {t("admin.sales.form.payment")}
          </CardTitle>
          <label className="flex items-center gap-2 self-end pb-2.5 font-semibold">
            <input
              type="checkbox"
              checked={paidInFull}
              onChange={(event) => setPaidInFull(event.target.checked)}
              className="size-4 accent-sea"
            />
            {t("admin.sales.form.paidInFull")}
          </label>
          <Field label={t("admin.sales.form.amountPaid")} htmlFor={id("amount_paid")} error={errors.amount_paid}>
            <Input
              id={id("amount_paid")}
              inputMode="decimal"
              value={paidInFull ? asTyped(totalExclTax) : amountPaid}
              disabled={paidInFull}
              onChange={(event) => setAmountPaid(event.target.value)}
              aria-invalid={errors.amount_paid ? true : undefined}
              autoComplete="off"
              className="num"
            />
          </Field>
          {select("payment_method", t("admin.sales.form.method"), method, setMethod, [
            { value: NO_METHOD, label: t("admin.sales.detail.none") },
            ...PAYMENT_METHODS.map((value) => ({ value, label: t(`admin.sales.methods.${value}`) })),
          ])}
          <Field label={t("admin.sales.form.reference")} htmlFor={id("payment_reference")}>
            <Input
              id={id("payment_reference")}
              value={reference}
              maxLength={50}
              onChange={(event) => setReference(event.target.value)}
            />
          </Field>
          {customer === WALK_IN && (
            <p className="col-span-4 text-[0.85rem] text-ink-2 max-[1000px]:col-span-2 max-[600px]:col-span-1">
              {t("admin.sales.form.walkInPays")}
            </p>
          )}
        </Card>

        <Card>
          <Field label={t("admin.sales.form.notes")} htmlFor={id("notes")} error={errors.notes}>
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
          <Button onClick={() => leave(back)}>{t("admin.sales.form.cancel")}</Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? t("admin.sales.form.saving") : t("admin.sales.form.saveDraft")}
          </Button>
          <Button variant="primary" disabled={save.isPending} onClick={() => submit(true)}>
            <Icon name="check" />
            {t("admin.sales.form.confirm")}
          </Button>
        </div>
      </form>
    </>
  );
}
