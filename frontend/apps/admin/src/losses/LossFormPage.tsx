import {
  addLossPhoto,
  type LossReasonEnum,
  type LossWrite,
  recordLoss,
  useGetStockSettings,
  useListLocations,
  useListLocationStock,
  useListProducts,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatQuantity, parseDecimalInput, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  Field,
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
import { type FormEvent, useId, useState } from "react";
import { Link, Navigate, useNavigate, useOutletContext } from "react-router";

import { toThousandths } from "../lib/decimal";
import { fieldErrors } from "../lib/errors";
import { pickable } from "../lib/pickable";
import { todayInTunis } from "../receipts/shared";
import { canRecordStockChecks, isOwner, LOSS_REASONS, refreshAfterStockCheck } from "./shared";

type Errors = Record<string, string>;

/** "Déclarer une perte": kilos thrown away at one place, why, and a photo when there is one. */
export function LossFormPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const formId = useId();

  // Archived ones leave the pickers unless this loss already uses them (pickable).
  const locations = useListLocations({ status: "all" });
  const products = useListProducts({ status: "all" });
  const settings = useGetStockSettings();

  const [location, setLocation] = useState("");
  const [product, setProduct] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState<LossReasonEnum | "">("");
  const [day, setDay] = useState(todayInTunis);
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [errors, setErrors] = useState<Errors>({});

  const stock = useListLocationStock(Number(location), { query: { enabled: location !== "" } });
  const available = stock.data?.find((row) => String(row.product_id) === product)?.quantity;

  const save = useMutation({
    mutationFn: async (payload: LossWrite) => {
      const saved = await recordLoss(payload);
      if (!photo) return { saved, photoFailed: false };
      try {
        return { saved: await addLossPhoto(saved.id, { photo }), photoFailed: false };
      } catch {
        return { saved, photoFailed: true };
      }
    },
    onSuccess: async ({ saved, photoFailed }) => {
      toast.success(
        t(saved.status === "pending" ? "admin.losses.form.pending" : "admin.losses.form.recorded", {
          number: saved.number,
        }),
      );
      if (photoFailed) toast.error(t("admin.losses.form.photoFailed"));
      await refreshAfterStockCheck(queryClient);
      void navigate(`/stock/pertes/${saved.id}`);
    },
    onError: (failure) => {
      const fromServer = fieldErrors(failure);
      setErrors(Object.keys(fromServer).length > 0 ? fromServer : { detail: t("admin.losses.form.error") });
    },
  });

  if (!canRecordStockChecks(session)) return <Navigate to="/stock/pertes" replace />;

  const parsed = parseDecimalInput(quantity.trim(), 3);
  const threshold = settings.data?.loss_approval_threshold;
  const willWait =
    !isOwner(session) &&
    threshold !== undefined &&
    parsed !== null &&
    !parsed.startsWith("-") &&
    toThousandths(parsed) > toThousandths(threshold);

  function submit(event: FormEvent) {
    event.preventDefault();
    const found: Errors = {};
    if (!location) found.location = t("admin.losses.form.required");
    if (!product) found.product = t("admin.losses.form.required");
    if (!reason) found.reason = t("admin.losses.form.required");
    if (!day) found.lost_on = t("admin.losses.form.required");
    if (parsed === null || parsed.startsWith("-") || /^0+(\.0+)?$/.test(parsed)) {
      found.quantity = t("admin.losses.form.weight");
    }
    setErrors(found);
    if (Object.keys(found).length > 0 || !reason || parsed === null) return;
    save.mutate({
      location: Number(location),
      product: Number(product),
      quantity: parsed,
      reason,
      lost_on: day,
      note: note.trim(),
    });
  }

  const id = (name: string) => `${formId}-${name}`;
  const select = (
    name: string,
    label: string,
    value: string,
    onChange: (value: string) => void,
    options: { value: string; label: string }[],
  ) => (
    <Field label={label} htmlFor={id(name)} error={errors[name]}>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id(name)} aria-invalid={errors[name] ? true : undefined}>
          <SelectValue placeholder={t("admin.losses.form.choose")} />
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
      <Link to="/stock/pertes" className="text-[0.85rem] font-semibold text-sea hover:underline">
        {t("admin.losses.back")}
      </Link>
      <PageHeader eyebrow={t("admin.losses.title")} title={t("admin.losses.form.title")} />

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Card className="grid grid-cols-2 gap-4 max-[640px]:grid-cols-1">
          {select(
            "location",
            t("admin.losses.form.location"),
            location,
            setLocation,
            pickable(locations.data ?? [], [location]).map((place) => ({ value: String(place.id), label: place.name })),
          )}
          {select(
            "product",
            t("admin.losses.form.product"),
            product,
            setProduct,
            pickable(products.data ?? [], [product]).map((one) => ({
              value: String(one.id),
              label: `${one.name} · ${one.reference}`,
            })),
          )}
          <Field label={t("admin.losses.form.quantity")} htmlFor={id("quantity")} error={errors.quantity}>
            <Input
              id={id("quantity")}
              inputMode="decimal"
              className="num"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              aria-invalid={errors.quantity ? true : undefined}
              autoComplete="off"
            />
          </Field>
          {select(
            "reason",
            t("admin.losses.form.reason"),
            reason,
            (value) => setReason(value as LossReasonEnum),
            LOSS_REASONS.map((value) => ({ value, label: t(`admin.losses.reasons.${value}`) })),
          )}
          <p className="col-span-full text-[0.85rem] text-ink-2" aria-live="polite">
            {[
              location && product && stock.data
                ? available
                  ? t("admin.losses.form.available", { quantity: formatQuantity(available) })
                  : t("admin.losses.form.notAvailable")
                : null,
              willWait && threshold ? t("admin.losses.form.willWait", { threshold: formatQuantity(threshold) }) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <Field label={t("admin.losses.form.date")} htmlFor={id("lost_on")} error={errors.lost_on}>
            <Input
              id={id("lost_on")}
              type="date"
              max={todayInTunis()}
              value={day}
              onChange={(event) => setDay(event.target.value)}
              aria-invalid={errors.lost_on ? true : undefined}
            />
          </Field>
          <Field label={t("admin.losses.form.photo")} htmlFor={id("photo")} error={errors.photo}>
            <input
              id={id("photo")}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => setPhoto(event.target.files?.[0] ?? null)}
              className="rounded-control border border-line bg-surface px-3 py-2 text-[0.9rem] text-ink"
            />
          </Field>
          <div className="col-span-full">
            <Field label={t("admin.losses.form.note")} htmlFor={id("note")} error={errors.note}>
              <textarea
                id={id("note")}
                rows={2}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                className="w-full rounded-control border border-line bg-surface px-3 py-2.5 text-ink"
              />
            </Field>
          </div>
        </Card>

        {errors.detail && (
          <p role="alert" className="rounded-chip bg-bad-soft px-3 py-2 text-[0.88rem] font-semibold text-bad">
            {errors.detail}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button onClick={() => void navigate("/stock/pertes")}>{t("admin.losses.form.cancel")}</Button>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            {save.isPending ? t("admin.losses.form.saving") : t("admin.losses.form.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
