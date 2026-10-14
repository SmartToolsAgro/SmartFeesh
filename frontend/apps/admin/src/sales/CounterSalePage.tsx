import {
  createSale,
  type SaleDetail,
  type SalePaymentMethodEnum,
  type SaleWrite,
  useListCustomers,
  useListLocationBatches,
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
  cn,
  Field,
  Icon,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { Link, Navigate, useOutletContext } from "react-router";

import { sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { amountsOf, filled, isShort, type Line, newLine, shownPrice } from "../lib/lines";
import { LinesGrid } from "../lib/LinesGrid";
import { type FormEvent, type ReactNode, useId, useMemo, useRef, useState } from "react";
import { Link, Navigate, useOutletContext } from "react-router";

import { isBelowMinimum, lineTotal, sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { usePartnerSuppliers } from "../partnerships/usePartnerSuppliers";
import { canSell, PAYMENT_METHODS, refreshAfterSale } from "./shared";

// Radix Select has no empty choice: this value stands for the walk-in customer ("Client de passage") and,
// for a lot, the oldest one first (FIFO, the default a seller can override, D-121).
const WALK_IN = "walk-in";
const AUTO_LOT = "fifo";

const asTyped = (value: string) => value.replace(".", ",");
const isPositive = (value: string | null): value is string =>
  value !== null && !value.startsWith("-") && !/^0+(\.0+)?$/.test(value);
// The messages the grid shows in its own cells; every other one goes in the alert.
const inGrid = (key: string) => /^lines\.\d+\.(product|quantity|unit_price|batch)$/.test(key);

/**
 * The lot a row takes its kilos from first. Lots of the row's product at this room, oldest first: a hint of
 * where they sit and who supplied them, never printed on a devis or a BL (D-121). FIFO stays the default;
 * picking one overrides it for the row.
 */
function LotCell({ room, line, onChange }: { room: string; line: Line; onChange: (batch: string) => void }) {
  const { t } = useTranslation();
  const batches = useListLocationBatches(Number(room), Number(line.product), {
    query: { enabled: room !== "" && line.product !== "" },
  });
  if (!line.product) return null;
  const chosen = (batches.data ?? []).find((option) => String(option.batch_id) === line.batch);
  return (
    <>
      <Select value={line.batch || AUTO_LOT} onValueChange={(value) => onChange(value === AUTO_LOT ? "" : value)}>
        <SelectTrigger
          aria-label={t("admin.sales.counterSale.lot")}
          className="border-0 bg-transparent px-2.5 py-2 [&>span]:truncate"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={AUTO_LOT}>{t("admin.sales.counterSale.lotAuto")}</SelectItem>
          {(batches.data ?? []).map((option) => (
            <SelectItem key={option.batch_id} value={String(option.batch_id)}>
              {t("admin.sales.counterSale.lotChoice", {
                batch: option.batch_number,
                supplier: option.supplier_name,
                location: option.location_name,
                quantity: formatQuantity(option.quantity),
              })}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {chosen && isShort(line.quantity, chosen.quantity) && (
        <p className="px-2.5 pb-1.5 text-[0.78rem] font-semibold text-bad">
          {t("admin.sales.counterSale.lotShort", { quantity: formatQuantity(chosen.quantity) })}
        </p>
      )}
    </>
  );
}

/** "Vente comptoir": weigh, type the rows of the basket, take the money. The sale is confirmed at once (D-052). */
export function CounterSalePage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const partners = usePartnerSuppliers(session);
  const queryClient = useQueryClient();
  const formId = useId();
  const id = (name: string) => `${formId}-${name}`;
  const nextKeyRef = useRef(0);

  const locations = useListLocations({ status: "active", kind: "cold_room" });
  const customers = useListCustomers({ status: "active" });
  const products = useListProducts({ status: "active" });
  const rooms = (locations.data ?? []).filter((location) => location.counter_sales);

  const [roomChoice, setRoomChoice] = useState("");
  const room = roomChoice || (rooms[0] ? String(rooms[0].id) : "");
  const [customer, setCustomer] = useState(WALK_IN);
  const [method, setMethod] = useState<SalePaymentMethodEnum>("cash");
  const [basket, setBasket] = useState<Line[]>(() => [newLine()]);
  // Counts the baskets started: a new one is a new grid, with the cursor back in its first cell.
  const [baskets, setBaskets] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [lastSale, setLastSale] = useState<SaleDetail | null>(null);

  const stock = useListLocationStock(Number(room), { query: { enabled: room !== "" } });
  const available = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const row of stock.data ?? []) byProduct.set(String(row.product_id), row.quantity);
    return byProduct;
  }, [stock.data]);
  const dailyPrice = useMemo(() => {
    const byProduct = new Map<string, string | null>();
    for (const product of products.data ?? []) byProduct.set(String(product.id), product.current_price);
    return byProduct;
  }, [products.data]);
  const realCustomer = customer !== WALK_IN;
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
  // The customer's own price list wins over the daily price, as on the server (D-049).
  const proposedPrice = (product: string): string | null => listPrice.get(product) ?? dailyPrice.get(product) ?? null;
  const priceOf = (line: Line): string => shownPrice(line, proposedPrice(line.product));
  const priceHint = (line: Line): string => {
    const fromList = listPrice.get(line.product);
    const inForce = dailyPrice.get(line.product);
    if (fromList && customerList) {
      return t("admin.sales.form.listPrice", { list: customerList.name, price: formatMoney(fromList) });
    }
    return inForce
      ? t("admin.sales.form.priceInForce", { price: formatMoney(inForce) })
      : t("admin.sales.form.noPrice");
  };

  function startBasket() {
    setBasket([newLine()]);
    setBaskets((count) => count + 1);
    setErrors({});
  }

  const collect = useMutation({
    mutationFn: (payload: SaleWrite) => createSale(payload),
    onSuccess: async (saved) => {
      toast.success(t("admin.sales.counterSale.done", { number: saved.number }));
      setLastSale(saved);
      startBasket();
      setCustomer(WALK_IN);
      await refreshAfterSale(queryClient);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.sales.counterSale.error") });
    },
  });

  if (!canSell(session)) return <Navigate to="/ventes" replace />;

  // The grid's blank rows are places to type in, not lines of the sale.
  const rows = filled(basket);
  const total = sum(basket.flatMap((line) => amountsOf(line, priceOf(line))?.amount ?? []));

  function pay() {
    const found: Record<string, string> = {};
    const lines: SaleWrite["lines"] = [];
    rows.forEach((line, index) => {
      const kg = parseDecimalInput(line.quantity.trim(), 3);
      const perKg = parseDecimalInput(priceOf(line).trim(), 3);
      if (!line.product) found[`lines.${index}.product`] = t("admin.sales.form.required");
      if (!isPositive(kg)) found[`lines.${index}.quantity`] = t("admin.sales.form.weight");
      if (!isPositive(perKg)) found[`lines.${index}.unit_price`] = t("admin.sales.form.money");
      lines.push({
        product: Number(line.product),
        quantity: kg ?? "",
        unit_price: perKg,
        batch: line.batch ? Number(line.batch) : null,
      });
    const kg = parseDecimalInput(quantity.trim(), 3);
    const perKg = parseDecimalInput(shownPrice.trim(), 3);
    if (!productRow) found.product = t("admin.sales.form.required");
    if (!isPositive(kg)) found.quantity = t("admin.sales.form.weight");
    if (!isPositive(perKg)) found.unit_price = t("admin.sales.form.money");
    setErrors(found);
    if (!productRow || !isPositive(kg) || !isPositive(perKg)) return;
    nextKeyRef.current += 1;
    const batch = batchChoice === AUTO_LOT ? "" : batchChoice;
    // The same product weighed twice stays one line (one line per product): its kilos add up, at the last
    // price and lot.
    setBasket((current) => {
      const same = current.find((line) => line.product === product);
      if (same) {
        const kilos = sum([same.quantity, kg]);
        return current.map((line) => (line === same ? { ...line, quantity: kilos, unit_price: perKg, batch } : line));
      }
      return [
        ...current,
        { key: nextKeyRef.current, product, name: productRow.name, quantity: kg, unit_price: perKg, batch },
      ];
    });
    setErrors(found);
    if (rows.length === 0 || !room || Object.keys(found).length > 0) return;
    collect.mutate({
      customer: realCustomer ? Number(customer) : null,
      location: Number(room),
      lines,
      paid_in_full: true,
      payment_method: method,
      confirm_now: true,
    });
  }

  const choose = (
    name: string,
    label: string,
    value: string,
    onChange: (value: string) => void,
    options: { value: string; label: string; detail?: ReactNode }[],
  ) => (
    <Field label={label} htmlFor={id(name)} error={errors[name]}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id(name)} aria-invalid={errors[name] ? true : undefined}>
          <SelectValue placeholder={t("admin.sales.form.choose")} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.detail ?? option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </Field>
  );
  const alerts = Object.entries(errors)
    .filter(([key]) => !inGrid(key))
    .map(([, message]) => message);

  return (
    <>
      <Link to="/ventes" className="text-[0.85rem] font-semibold text-sea hover:underline">
        {t("admin.sales.back")}
      </Link>
      <PageHeader eyebrow={t("admin.sales.title")} title={t("admin.sales.counterSale.title")} />
      <p className="text-ink-2">{t("admin.sales.counterSale.intro")}</p>

      {locations.data && rooms.length === 0 ? (
        <p role="alert" className="text-bad">
          {t("admin.sales.counterSale.noRoom")}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <Card className="grid grid-cols-2 gap-4 max-[600px]:grid-cols-1">
            {choose(
              "location",
              t("admin.sales.counterSale.room"),
              room,
              (value) => {
                setRoomChoice(value);
                startBasket();
              },
              rooms.map((option) => ({ value: String(option.id), label: option.name })),
            )}
            {choose("customer", t("admin.sales.counterSale.customer"), customer, setCustomer, [
              { value: WALK_IN, label: t("admin.sales.form.walkIn") },
              ...(customers.data ?? [])
                .filter((option) => !option.is_walk_in)
                .map((option) => ({ value: String(option.id), label: `${option.name} · ${option.reference}` })),
            ])}
          </Card>
        <div className="grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] items-start gap-4 max-[1000px]:grid-cols-1">
          <div className="flex flex-col gap-4">
            <Card className="grid grid-cols-2 gap-4 max-[600px]:grid-cols-1">
              {choose(
                "location",
                t("admin.sales.counterSale.room"),
                room,
                (value) => {
                  setRoomChoice(value);
                  setBasket([]);
                },
                rooms.map((option) => ({ value: String(option.id), label: option.name })),
              )}
              {choose("customer", t("admin.sales.counterSale.customer"), customer, setCustomer, [
                { value: WALK_IN, label: t("admin.sales.form.walkIn") },
                ...(customers.data ?? [])
                  .filter((option) => !option.is_walk_in)
                  .map((option) => ({ value: String(option.id), label: `${option.name} · ${option.reference}` })),
              ])}
            </Card>

            <Card>
              <form
                onSubmit={add}
                noValidate
                className="grid grid-cols-[2fr_1fr_1fr] items-end gap-4 max-[700px]:grid-cols-2"
              >
                <div className="max-[700px]:col-span-2">
                  {choose(
                    "product",
                    t("admin.sales.counterSale.product"),
                    product,
                    (value) => {
                      setProduct(value);
                      setPriceTouched(false);
                      setPrice("");
                      setBatchChoice(AUTO_LOT);
                    },
                    (products.data ?? []).map((option) => ({
                      value: String(option.id),
                      label: `${option.name} · ${option.reference}`,
                    })),
                  )}
                </div>
                {product && (
                  <div className="col-span-2 max-[700px]:col-span-2">
                    {choose("batch", t("admin.sales.counterSale.lot"), batchChoice, setBatchChoice, [
                      { value: AUTO_LOT, label: t("admin.sales.counterSale.lotAuto") },
                      ...(batches.data ?? []).map((option) => {
                        // Green place, yellow lot, grey supplier, gold when the supplier is a partner (D-060).
                        const partner = partners?.has(option.supplier_id) ?? false;
                        return {
                          value: String(option.batch_id),
                          label: t("admin.sales.counterSale.lotChoice", {
                            batch: option.batch_number,
                            supplier: option.supplier_name,
                            location: option.location_name,
                            quantity: formatQuantity(option.quantity),
                          }),
                          detail: (
                            <span className="flex flex-col gap-0.5 leading-snug">
                              <span className="font-semibold text-good">{option.location_name}</span>
                              <span>
                                <span className="num font-semibold text-lot">{option.batch_number}</span>
                                <span className="text-ink-2">
                                  {" · "}
                                  {t("admin.sales.counterSale.lotDetail", {
                                    quantity: formatQuantity(option.quantity),
                                  })}
                                </span>
                              </span>
                              <span className={cn(partner ? "font-semibold text-gold" : "text-ink-2")}>
                                {option.supplier_name}
                                {partner && ` · ${t("admin.sales.counterSale.partnerTag")}`}
                              </span>
                            </span>
                          ),
                        };
                      }),
                    ])}
                    {chosenBatch &&
                      isPositive(parseDecimalInput(quantity.trim(), 3)) &&
                      Number(parseDecimalInput(quantity.trim(), 3)) > Number(chosenBatch.quantity) && (
                        <p className="mt-1 text-[0.8rem] font-semibold text-bad">
                          {t("admin.sales.counterSale.lotShort", { quantity: formatQuantity(chosenBatch.quantity) })}
                        </p>
                      )}
                  </div>
                )}
                <Field label={t("admin.sales.counterSale.quantity")} htmlFor={id("quantity")} error={errors.quantity}>
                  <Input
                    id={id("quantity")}
                    inputMode="decimal"
                    autoComplete="off"
                    value={quantity}
                    onChange={(event) => setQuantity(event.target.value)}
                    aria-invalid={errors.quantity ? true : undefined}
                    className={BIG_INPUT}
                  />
                </Field>
                <Field label={t("admin.sales.counterSale.price")} htmlFor={id("unit_price")} error={errors.unit_price}>
                  <Input
                    id={id("unit_price")}
                    inputMode="decimal"
                    autoComplete="off"
                    value={shownPrice}
                    onChange={(event) => {
                      setPrice(event.target.value);
                      setPriceTouched(true);
                    }}
                    aria-invalid={errors.unit_price ? true : undefined}
                    className={BIG_INPUT}
                  />
                </Field>
                {productRow && isBelowMinimum(parseDecimalInput(shownPrice.trim(), 3), productRow.min_price) && (
                  <p
                    role="alert"
                    className="col-span-3 rounded-chip bg-bad-soft px-3 py-2 text-[0.85rem] font-semibold text-bad max-[700px]:col-span-2"
                  >
                    {t("admin.sales.form.belowMinimum", { minimum: formatMoney(productRow.min_price ?? "0") })}
                  </p>
                )}
                <p className="col-span-2 text-[0.85rem] text-ink-2 max-[700px]:col-span-2" aria-live="polite">
                  {product && stock.data
                    ? available.get(product)
                      ? t("admin.sales.form.available", {
                          location: rooms.find((option) => String(option.id) === room)?.name ?? "",
                          quantity: formatQuantity(available.get(product) ?? "0"),
                        })
                      : t("admin.sales.form.notAvailable", {
                          location: rooms.find((option) => String(option.id) === room)?.name ?? "",
                        })
                    : ""}
                </p>
                <Button type="submit" className="max-[700px]:col-span-2">
                  <Icon name="plus" />
                  {t("admin.sales.counterSale.add")}
                </Button>
              </form>
            </Card>
          </div>

          <Card className="flex flex-col gap-3" aria-labelledby={id("basket")} role="region">
            <CardTitle id={id("basket")} className="mb-0">
              {t("admin.sales.counterSale.basket")}
            </CardTitle>
            <LinesGrid
              key={baskets}
              autoFocus
              label={t("admin.sales.counterSale.basket")}
              lines={basket}
              onChange={setBasket}
              products={products.data ?? []}
              proposedPrice={proposedPrice}
              stock={stock.data ? available : undefined}
              errors={errors}
              extra={{
                header: t("admin.sales.counterSale.lot"),
                field: "batch",
                cell: (line, change) => <LotCell room={room} line={line} onChange={(batch) => change({ batch })} />,
              }}
              hint={priceHint}
            />
          </Card>

          <Card className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3">
            <div role="group" aria-label={t("admin.sales.counterSale.method")} className="flex flex-wrap gap-2">
              {PAYMENT_METHODS.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={method === value}
                  onClick={() => setMethod(value)}
                  className={cn(
                    "rounded-control border border-line px-3 py-2 text-[0.9rem] font-semibold text-ink-2",
                    method === value && "border-sea bg-sea-soft text-sea",
                  )}
                >
                  {t(`admin.sales.methods.${value}`)}
                </button>
              ))}
            </div>
            <div className="ms-auto flex flex-wrap items-center gap-x-6 gap-y-3">
              <p className="flex items-baseline gap-3">
                <span className="font-semibold">{t("admin.sales.counterSale.total")}</span>
                <span className="num text-[1.8rem] font-bold" aria-live="polite">
                  {formatMoney(total)}
                </span>
              </p>
              <Button variant="primary" disabled={rows.length === 0 || collect.isPending} onClick={pay}>
                <Icon name="cash" />
                {collect.isPending
                  ? t("admin.sales.counterSale.collecting")
                  : t("admin.sales.counterSale.collect", { total: formatMoney(total) })}
              </Button>
            </div>
            {alerts.length > 0 && (
              <p
                role="alert"
                className="w-full rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad"
              >
                {alerts.join(" ")}
              </p>
            )}
            {lastSale && (
              <p role="status" className="w-full text-[0.9rem] text-ink-2">
                {t("admin.sales.counterSale.done", { number: lastSale.number })}{" "}
                <Link to={`/ventes/${lastSale.id}`} className="font-semibold text-sea hover:underline">
                  {t("admin.sales.counterSale.open")}
                </Link>
              </p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
