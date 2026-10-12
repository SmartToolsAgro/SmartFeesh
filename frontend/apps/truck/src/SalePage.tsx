import {
  ApiError,
  type CustomerChoice,
  type MyStockLine,
  type SaleDetail,
  useCreateSale,
  useListMyCustomers,
  useListMyStock,
} from "@frutti/api";
import { useSession } from "@frutti/auth";
import { formatMoney, formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState, Input } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

// Every text the server put in an error answer, so the driver reads why a sale was refused.
function messagesOf(body: unknown): string[] {
  if (typeof body === "string") return [body];
  if (Array.isArray(body)) return body.flatMap(messagesOf);
  if (typeof body === "object" && body !== null) return Object.values(body).flatMap(messagesOf);
  return [];
}

// Millimes, so sums of prices stay exact.
const millimes = (value: string) => Math.round(Number(value) * 1000);

// "Vente": customer, then goods, then payment, then the receipt. One question per screen.
export function SalePage() {
  const { t } = useTranslation();
  const session = useSession();
  const queryClient = useQueryClient();
  const truck = session.data?.truck ?? null;
  const stock = useListMyStock({ query: { enabled: truck !== null, retry: false } });
  const [customer, setCustomer] = useState<CustomerChoice | null>(null);
  const [kilos, setKilos] = useState<Record<number, string>>({});
  const [paid, setPaid] = useState<string | null>(null);
  const [step, setStep] = useState<"goods" | "pay">("goods");
  const [receipt, setReceipt] = useState<SaleDetail | null>(null);
  const [uuid, setUuid] = useState(() => crypto.randomUUID());
  const [error, setError] = useState("");
  const create = useCreateSale({
    mutation: {
      onSuccess: (sale) => {
        setReceipt(sale);
        void queryClient.invalidateQueries();
      },
      onError: (failure) => {
        const texts = failure instanceof ApiError ? messagesOf(failure.body) : [];
        setError(texts.join(" ") || t("truck.sale.failed"));
      },
    },
  });

  if (truck === null) {
    return (
      <EmptyState illustration="truck" title={t("truck.day.noTruck")}>
        {t("truck.sale.needTruck")}
      </EmptyState>
    );
  }
  if (receipt !== null) {
    return (
      <Receipt
        sale={receipt}
        onNew={() => {
          setReceipt(null);
          setCustomer(null);
          setKilos({});
          setPaid(null);
          setStep("goods");
          setError("");
          setUuid(crypto.randomUUID());
        }}
      />
    );
  }
  if (customer === null) return <PickCustomer onPick={setCustomer} />;

  const lines = (stock.data ?? []).filter((line) => Number(kilos[line.product_id] ?? 0) > 0);
  const lineMillimes = (line: MyStockLine) =>
    Math.round(Number(kilos[line.product_id] ?? 0) * millimes(line.unit_price ?? "0"));
  const totalMillimes = lines.reduce((sum, line) => sum + lineMillimes(line), 0);
  const totalText = (totalMillimes / 1000).toFixed(3);
  const paidText = paid ?? totalText;
  const paidValue = parseDecimalInput(paidText.trim(), 3);
  const tooMuch = paidValue !== null && millimes(paidValue) > totalMillimes;
  const owedMillimes = paidValue === null ? 0 : Math.max(totalMillimes - millimes(paidValue), 0);

  const confirm = () => {
    if (paidValue === null || tooMuch) return;
    setError("");
    create.mutate({
      data: {
        customer: customer.is_walk_in ? null : customer.id,
        location: truck.location_id,
        confirm_now: true,
        client_uuid: uuid,
        amount_paid: paidValue,
        payment_method: "cash",
        lines: lines.map((line) => ({ product: line.product_id, quantity: kilos[line.product_id] ?? "" })),
      },
    });
  };

  return (
    <div className="space-y-4">
      <Card className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-ink-2">{t("truck.sale.customer")}</p>
          <p className="text-xl font-bold">{customer.name}</p>
        </div>
        <Button onClick={() => setCustomer(null)}>{t("truck.sale.change")}</Button>
      </Card>
      {step === "goods" ? (
        <>
          {stock.isLoading ? null : (stock.data ?? []).length === 0 ? (
            <EmptyState illustration="fridge" title={t("truck.sale.emptyTruck")}>
              {t("truck.sale.emptyTruckBody")}
            </EmptyState>
          ) : (
            <Card>
              <h2 className="mb-3">{t("truck.sale.howMuch")}</h2>
              <ul className="divide-y divide-line">
                {(stock.data ?? []).map((line) => (
                  <li key={line.product_id} className="space-y-2 py-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-lg font-semibold">{line.product_name}</span>
                      <span className="text-sm text-ink-2">
                        {t("truck.sale.left", { kg: formatQuantity(line.quantity) })}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Input
                        inputMode="decimal"
                        aria-label={line.product_name}
                        placeholder="0"
                        className="text-xl"
                        value={kilos[line.product_id] ?? ""}
                        onChange={(event) => setKilos({ ...kilos, [line.product_id]: event.target.value })}
                      />
                      <span className="shrink-0 text-lg font-semibold">kg</span>
                    </div>
                    {line.unit_price === null ? null : (
                      <p className="text-sm text-ink-2">{formatMoney(line.unit_price)} / kg</p>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card className="space-y-3">
            <p className="flex items-baseline justify-between">
              <span>{t("truck.sale.total")}</span>
              <span className="text-2xl font-bold">{formatMoney(totalText)}</span>
            </p>
            <Button
              size="lg"
              variant="primary"
              className="py-4 text-lg"
              disabled={lines.length === 0}
              onClick={() => setStep("pay")}
            >
              {t("truck.sale.next")}
            </Button>
          </Card>
        </>
      ) : (
        <Card className="space-y-4">
          <p className="flex items-baseline justify-between">
            <span>{t("truck.sale.total")}</span>
            <span className="text-2xl font-bold">{formatMoney(totalText)}</span>
          </p>
          <div className="space-y-1">
            <label htmlFor="paid" className="font-semibold">
              {t("truck.sale.paid")}
            </label>
            <Input
              id="paid"
              inputMode="decimal"
              className="text-2xl"
              value={paidText}
              aria-invalid={paidValue === null || tooMuch}
              onChange={(event) => setPaid(event.target.value)}
            />
          </div>
          {tooMuch ? <p className="text-bad">{t("truck.sale.tooMuch")}</p> : null}
          {owedMillimes > 0 && !tooMuch ? (
            <p className="text-lg font-semibold">
              {t("truck.sale.onCredit", { amount: formatMoney((owedMillimes / 1000).toFixed(3)) })}
            </p>
          ) : null}
          {error === "" ? null : <p className="text-bad">{error}</p>}
          <Button
            size="lg"
            variant="primary"
            className="py-4 text-lg"
            disabled={paidValue === null || tooMuch || create.isPending}
            onClick={confirm}
          >
            {t("truck.sale.confirm")}
          </Button>
          <Button size="lg" onClick={() => setStep("goods")}>
            {t("truck.sale.back")}
          </Button>
        </Card>
      )}
    </div>
  );
}

function PickCustomer({ onPick }: { onPick: (customer: CustomerChoice) => void }) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const customers = useListMyCustomers({ search: search.trim() });
  return (
    <div className="space-y-3">
      <h2>{t("truck.sale.whoFor")}</h2>
      <Input
        type="search"
        aria-label={t("truck.sale.search")}
        placeholder={t("truck.sale.search")}
        className="text-lg"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      {(customers.data ?? []).map((customer) => (
        <Button
          key={customer.id}
          size="lg"
          variant={customer.is_walk_in ? "secondary" : "primary"}
          className="flex-col py-4 text-xl"
          onClick={() => onPick(customer)}
        >
          <span>{customer.name}</span>
          {customer.city === "" ? null : <span className="text-sm font-normal">{customer.city}</span>}
        </Button>
      ))}
    </div>
  );
}

function Receipt({ sale, onNew }: { sale: SaleDetail; onNew: () => void }) {
  const { t } = useTranslation();
  const text = [
    `${sale.number} · ${sale.customer.name}`,
    ...sale.lines.map(
      (line) =>
        `${line.product.name}: ${formatQuantity(line.quantity)} kg × ${formatMoney(line.unit_price)} = ${formatMoney(line.amount)}`,
    ),
    `${t("truck.sale.total")}: ${formatMoney(sale.total)}`,
    `${t("truck.sale.paid")}: ${formatMoney(sale.amount_paid)}`,
    ...(Number(sale.amount_due) > 0 ? [`${t("truck.sale.stillOwed")}: ${formatMoney(sale.amount_due)}`] : []),
  ].join("\n");
  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <p className="text-xl font-bold">{t("truck.sale.done", { number: sale.number })}</p>
        <p className="text-ink-2">{sale.customer.name}</p>
        <ul className="divide-y divide-line">
          {sale.lines.map((line) => (
            <li key={line.id} className="flex items-baseline justify-between gap-3 py-2">
              <span>
                {line.product.name} · {formatQuantity(line.quantity)} kg
              </span>
              <span className="font-semibold">{formatMoney(line.amount)}</span>
            </li>
          ))}
        </ul>
        <p className="flex justify-between text-xl font-bold">
          <span>{t("truck.sale.total")}</span>
          <span>{formatMoney(sale.total)}</span>
        </p>
        <p className="flex justify-between">
          <span>{t("truck.sale.paid")}</span>
          <span>{formatMoney(sale.amount_paid)}</span>
        </p>
        {Number(sale.amount_due) > 0 ? (
          <p className="flex justify-between font-semibold">
            <span>{t("truck.sale.stillOwed")}</span>
            <span>{formatMoney(sale.amount_due)}</span>
          </p>
        ) : null}
      </Card>
      {typeof navigator.share === "function" ? (
        <Button size="lg" className="py-4 text-lg" onClick={() => void navigator.share({ title: sale.number, text })}>
          {t("truck.sale.share")}
        </Button>
      ) : null}
      <Button size="lg" variant="primary" className="py-4 text-lg" onClick={onNew}>
        {t("truck.sale.newSale")}
      </Button>
    </div>
  );
}
