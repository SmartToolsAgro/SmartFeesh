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
  Input,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useMemo, useRef, useState } from "react";
import { Link, Navigate, useOutletContext } from "react-router";

import { isBelowMinimum, lineTotal, sum } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { canSell, PAYMENT_METHODS, refreshAfterSale } from "./shared";

type BasketLine = {
  key: number;
  product: string;
  name: string;
  quantity: string;
  unit_price: string;
  batch: string;
};

// Radix Select has no empty choice: this value stands for the walk-in customer ("Client de passage") and,
// for a lot, the oldest one first (FIFO, the default a seller can override, D-121).
const WALK_IN = "walk-in";
const AUTO_LOT = "fifo";
const BIG_INPUT = "num py-3 text-[1.6rem] font-semibold";

const asTyped = (value: string) => value.replace(".", ",");
const isPositive = (value: string | null): value is string =>
  value !== null && !value.startsWith("-") && !/^0+(\.0+)?$/.test(value);

/** "Vente comptoir": weigh, add to the basket, take the money. The sale is confirmed at once (D-052). */
export function CounterSalePage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
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
  const [product, setProduct] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [priceTouched, setPriceTouched] = useState(false);
  const [batchChoice, setBatchChoice] = useState(AUTO_LOT);
  const [method, setMethod] = useState<SalePaymentMethodEnum>("cash");
  const [basket, setBasket] = useState<BasketLine[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [lastSale, setLastSale] = useState<SaleDetail | null>(null);

  const stock = useListLocationStock(Number(room), { query: { enabled: room !== "" } });
  const available = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const row of stock.data ?? []) byProduct.set(String(row.product_id), row.quantity);
    return byProduct;
  }, [stock.data]);
  // Lots of the chosen product at this room, oldest first: a hint of where they sit and who supplied them,
  // never printed on a devis or a BL (D-121). FIFO stays the default; picking one overrides it for the line.
  const batches = useListLocationBatches(Number(room), Number(product), {
    query: { enabled: room !== "" && product !== "" },
  });
  const chosenBatch = (batches.data ?? []).find((option) => String(option.batch_id) === batchChoice);
  const realCustomer = customer !== WALK_IN;
  const priceLists = useListPriceLists(
    { customer: Number(customer), status: "active" },
    { query: { enabled: realCustomer } },
  );
  const listPrice = useMemo(() => {
    const byProduct = new Map<string, string>();
    for (const item of (realCustomer ? priceLists.data?.[0]?.items : undefined) ?? []) {
      byProduct.set(String(item.product), item.price);
    }
    return byProduct;
  }, [priceLists.data, realCustomer]);
  const productRow = (products.data ?? []).find((option) => String(option.id) === product);
  const proposed = product ? (listPrice.get(product) ?? productRow?.current_price ?? null) : null;
  const shownPrice = priceTouched ? price : proposed ? asTyped(proposed) : "";

  const collect = useMutation({
    mutationFn: (payload: SaleWrite) => createSale(payload),
    onSuccess: async (saved) => {
      toast.success(t("admin.sales.counterSale.done", { number: saved.number }));
      setLastSale(saved);
      setBasket([]);
      setErrors({});
      setCustomer(WALK_IN);
      await refreshAfterSale(queryClient);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.sales.counterSale.error") });
    },
  });

  if (!canSell(session)) return <Navigate to="/ventes" replace />;

  const amounts = basket.map((line) => lineTotal(line.quantity, line.unit_price));
  const total = sum(amounts);

  function add(event: FormEvent) {
    event.preventDefault();
    const found: Record<string, string> = {};
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
      return [...current, { key: nextKeyRef.current, product, name: productRow.name, quantity: kg, unit_price: perKg, batch }];
    });
    setProduct("");
    setQuantity("");
    setPrice("");
    setPriceTouched(false);
    setBatchChoice(AUTO_LOT);
  }

  function pay() {
    if (basket.length === 0 || !room) return;
    collect.mutate({
      customer: realCustomer ? Number(customer) : null,
      location: Number(room),
      lines: basket.map((line) => ({
        product: Number(line.product),
        quantity: line.quantity,
        unit_price: line.unit_price,
        batch: line.batch ? Number(line.batch) : null,
      })),
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
    options: { value: string; label: string }[],
  ) => (
    <Field label={label} htmlFor={id(name)} error={errors[name]}>
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
  // The add form shows its own fields' errors, each basket row its kilos; everything else goes in the alert.
  const shownElsewhere = (key: string) =>
    ["product", "quantity", "unit_price"].includes(key) || /^lines\.\d+\.quantity$/.test(key);
  const alerts = Object.entries(errors)
    .filter(([key]) => !shownElsewhere(key))
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
                      ...(batches.data ?? []).map((option) => ({
                        value: String(option.batch_id),
                        label: t("admin.sales.counterSale.lotChoice", {
                          batch: option.batch_number,
                          supplier: option.supplier_name,
                          location: option.location_name,
                          quantity: formatQuantity(option.quantity),
                        }),
                      })),
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
            {basket.length === 0 ? (
              <p className="text-ink-2">{t("admin.sales.counterSale.emptyBasket")}</p>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>{t("admin.sales.detail.product")}</Th>
                    <Th numeric>{t("admin.sales.detail.quantity")}</Th>
                    <Th numeric>{t("admin.sales.detail.price")}</Th>
                    <Th numeric>{t("admin.sales.detail.amount")}</Th>
                    <Th>
                      <span className="sr-only">{t("admin.sales.form.removeLine")}</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {basket.map((line, index) => (
                    <tr key={line.key}>
                      <Td>
                        {line.name}
                        {errors[`lines.${index}.quantity`] && (
                          <p className="text-[0.78rem] font-semibold text-bad">{errors[`lines.${index}.quantity`]}</p>
                        )}
                      </Td>
                      <Td numeric className="whitespace-nowrap">
                        {formatQuantity(line.quantity)}
                      </Td>
                      <Td numeric className="whitespace-nowrap">
                        {formatMoney(line.unit_price)}
                      </Td>
                      <Td numeric className="font-semibold whitespace-nowrap">
                        {formatMoney(amounts[index] ?? "0")}
                      </Td>
                      <Td>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={t("admin.sales.counterSale.remove", { product: line.name })}
                          onClick={() => setBasket((current) => current.filter((other) => other.key !== line.key))}
                        >
                          <Icon name="trash" />
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            <div className="flex items-baseline justify-between gap-4 border-t-2 border-ink pt-2">
              <span className="font-semibold">{t("admin.sales.counterSale.total")}</span>
              <span className="num text-[1.8rem] font-bold" aria-live="polite">
                {formatMoney(total)}
              </span>
            </div>
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
            {alerts.length > 0 && (
              <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
                {alerts.join(" ")}
              </p>
            )}
            <Button variant="primary" size="lg" disabled={basket.length === 0 || collect.isPending} onClick={pay}>
              <Icon name="cash" />
              {collect.isPending
                ? t("admin.sales.counterSale.collecting")
                : t("admin.sales.counterSale.collect", { total: formatMoney(total) })}
            </Button>
            {lastSale && (
              <p role="status" className="text-[0.9rem] text-ink-2">
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
