import type { Customer, Product } from "@frutti/api";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  CardTitle,
  Field,
  Icon,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@frutti/ui";
import { useId } from "react";

import { BoxCountsFields } from "../boxes/BoxCountsFields";
import { lineTotal, sum } from "../lib/decimal";
import { pickable } from "../lib/pickable";
import { type Line, type Part, addressOf, asTyped, lineKey, newLine, scopedErrors } from "./formLines";

/**
 * The part of a truck load that is for one client (D-160): who, where it is delivered (the client's address,
 * changeable for this load's BL only), what they buy and the boxes they get. Each client gets a BL of their own.
 */
export function ClientPart({
  index,
  part,
  customers,
  products,
  availableOf,
  priceInForce,
  errors,
  onChange,
  onRemove,
}: {
  index: number;
  part: Part;
  customers: readonly Customer[];
  products: readonly Product[];
  availableOf: ReadonlyMap<string, string>;
  priceInForce: ReadonlyMap<string, string | null>;
  errors: Record<string, string>;
  onChange: (next: Part) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const formId = useId();
  const own = scopedErrors(errors, `deliveries.${index}.`);
  const id = (name: string) => `${formId}-${name}`;
  const customer = customers.find((candidate) => String(candidate.id) === part.customer);

  const priceOf = (line: Line): string => {
    if (line.priceTouched) return line.unit_price;
    const price = priceInForce.get(line.product);
    return price ? asTyped(price) : "";
  };
  const setLine = (key: number, change: Partial<Line>) =>
    onChange({ ...part, lines: part.lines.map((line) => (line.key === key ? { ...line, ...change } : line)) });

  const amounts = part.lines.flatMap((line) => {
    const quantity = parseDecimalInput(line.quantity.trim(), 3);
    const price = parseDecimalInput(priceOf(line).trim(), 3);
    return quantity && price && !quantity.startsWith("-") && !price.startsWith("-") ? [lineTotal(quantity, price)] : [];
  });

  return (
    <Card
      className="flex flex-col gap-3 border-sea/40"
      role="group"
      aria-label={t("admin.transfers.form.clientNumber", { number: index + 1 })}
    >
      <div className="flex flex-wrap items-center gap-3">
        <CardTitle className="mb-0">
          {customer?.name ?? t("admin.transfers.form.clientNumber", { number: index + 1 })}
        </CardTitle>
        <Button
          className="ms-auto"
          size="icon"
          variant="ghost"
          aria-label={t("admin.transfers.form.removeClient")}
          title={t("admin.transfers.form.removeClient")}
          onClick={onRemove}
        >
          <Icon name="trash" />
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 max-[800px]:grid-cols-1">
        <Field label={t("admin.transfers.form.client")} htmlFor={id("customer")} error={own.customer}>
          <Select
            value={part.customer}
            onValueChange={(value) =>
              onChange({
                ...part,
                customer: value,
                address: addressOf(customers.find((candidate) => String(candidate.id) === value)),
              })
            }
          >
            <SelectTrigger id={id("customer")} aria-invalid={own.customer ? true : undefined}>
              <SelectValue placeholder={t("admin.transfers.form.choose")} />
            </SelectTrigger>
            <SelectContent>
              {pickable(customers, [part.customer]).map((candidate) => (
                <SelectItem key={candidate.id} value={String(candidate.id)}>
                  {candidate.name} · {candidate.reference}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label={t("admin.transfers.form.deliveryAddress")} htmlFor={id("address")} error={own.delivery_address}>
          <Input
            id={id("address")}
            value={part.address}
            maxLength={255}
            autoComplete="off"
            onChange={(event) => onChange({ ...part, address: event.target.value })}
          />
        </Field>
      </div>
      <p className="text-[0.85rem] text-ink-2">{t("admin.transfers.form.deliveryAddressHint")}</p>

      {part.lines.map((line, lineIndex) => {
        const available = line.product ? availableOf.get(line.product) : undefined;
        const input = (field: "quantity" | "unit_price", label: string) => (
          <Field label={label} htmlFor={id(`${field}-${line.key}`)} error={own[lineKey(lineIndex, field)]}>
            <Input
              id={id(`${field}-${line.key}`)}
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
              aria-invalid={own[lineKey(lineIndex, field)] ? true : undefined}
              autoComplete="off"
              className="num"
            />
          </Field>
        );
        return (
          <div
            key={line.key}
            className="grid grid-cols-[2fr_1fr_1fr_auto] items-start gap-3 rounded-card border border-line p-3 max-[800px]:grid-cols-2"
          >
            <Field
              label={t("admin.transfers.form.product")}
              htmlFor={id(`product-${line.key}`)}
              error={own[lineKey(lineIndex, "product")]}
              className="max-[800px]:col-span-2"
            >
              <Select value={line.product} onValueChange={(value) => setLine(line.key, { product: value })}>
                <SelectTrigger
                  id={id(`product-${line.key}`)}
                  aria-invalid={own[lineKey(lineIndex, "product")] ? true : undefined}
                >
                  <SelectValue placeholder={t("admin.transfers.form.choose")} />
                </SelectTrigger>
                <SelectContent>
                  {pickable(
                    products,
                    part.lines.map((item) => item.product),
                  ).map((product) => (
                    <SelectItem key={product.id} value={String(product.id)}>
                      {product.name} · {product.reference}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            {input("quantity", t("admin.transfers.form.quantity"))}
            {input("unit_price", t("admin.transfers.form.price"))}
            <div className="flex items-end self-stretch max-[800px]:col-span-2 max-[800px]:justify-end">
              <Button
                size="icon"
                variant="ghost"
                aria-label={t("admin.transfers.form.removeLine")}
                title={t("admin.transfers.form.removeLine")}
                onClick={() => onChange({ ...part, lines: part.lines.filter((other) => other.key !== line.key) })}
              >
                <Icon name="trash" />
              </Button>
            </div>
            {line.product && available !== undefined && (
              <p className="col-span-full text-[0.85rem] text-ink-2">
                {t("admin.transfers.form.available", { quantity: formatQuantity(available) })}
              </p>
            )}
          </div>
        );
      })}
      {own.lines && <p className="text-[0.78rem] font-semibold text-bad">{own.lines}</p>}
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
        <Button onClick={() => onChange({ ...part, lines: [...part.lines, newLine()] })}>
          <Icon name="plus" />
          {t("admin.transfers.form.addLine")}
        </Button>
        <dl className="ms-auto">
          <dt className="text-[0.78rem] font-semibold text-ink-2">{t("admin.transfers.form.clientTotal")}</dt>
          <dd className="num font-bold">{formatMoney(sum(amounts))}</dd>
        </dl>
      </div>

      <BoxCountsFields
        title={t("admin.transfers.form.clientBoxesTitle")}
        hint={t("admin.transfers.form.clientBoxesHint")}
        value={part.boxes}
        onChange={(boxes) => onChange({ ...part, boxes })}
        errors={own}
      />
    </Card>
  );
}
