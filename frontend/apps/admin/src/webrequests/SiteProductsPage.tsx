import {
  addSiteProduct,
  getListSiteProductsQueryKey,
  type OfficeSiteProduct,
  type PatchedSiteProductUpdate,
  type Product,
  removeSiteProduct,
  updateSiteProduct,
  useListProducts,
  useListSiteProducts,
} from "@frutti/api";
import type { Session } from "@frutti/auth";
import { formatMoney, parseDecimalInput, useTranslation } from "@frutti/i18n";
import {
  Button,
  Card,
  Combobox,
  type ComboboxOption,
  ConfirmButton,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  EmptyState,
  Field,
  Icon,
  Input,
  PageHeader,
  Pill,
  Table,
  Td,
  Th,
  toast,
} from "@frutti/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useOutletContext } from "react-router";

import { fieldErrors } from "../lib/errors";
import { canRecordReceipts } from "../receipts/shared";

/** "" → null ("prix sur demande"); "28,5" → "28.5"; anything else → undefined (not a price). */
function parseWebPrice(text: string): string | null | undefined {
  if (text.trim() === "") return null;
  const value = parseDecimalInput(text, 3);
  return value === null || value.startsWith("-") ? undefined : value;
}

/** The products the public site shows, with their own web price (D-186). The day's price is not touched. */
export function SiteProductsPage() {
  const { t } = useTranslation();
  const session = useOutletContext<Session>();
  const canEdit = canRecordReceipts(session);
  const queryClient = useQueryClient();
  const rows = useListSiteProducts();
  const products = useListProducts({ status: "active" });
  const [adding, setAdding] = useState(false);
  const dayPrices = useMemo(
    () => new Map((products.data ?? []).map((product) => [product.id, product.current_price])),
    [products.data],
  );

  const refresh = () => queryClient.invalidateQueries({ queryKey: getListSiteProductsQueryKey() });
  const failed = (failure: unknown) => {
    const fromServer = fieldErrors(failure);
    toast.error(Object.values(fromServer)[0] ?? t("admin.siteProducts.actionError"));
  };
  const update = useMutation({
    mutationFn: ({ id, changes }: { id: number; changes: PatchedSiteProductUpdate }) => updateSiteProduct(id, changes),
    onSuccess: async () => {
      toast.success(t("admin.siteProducts.saved"));
      await refresh();
    },
    onError: failed,
  });
  const remove = useMutation({
    mutationFn: (row: OfficeSiteProduct) => removeSiteProduct(row.id),
    onSuccess: async (_, row) => {
      toast.success(t("admin.siteProducts.removed", { name: row.product_name }));
      await refresh();
    },
    onError: failed,
  });
  // Moving a row renumbers the list 0, 1, 2... and sends only the positions that change.
  const move = useMutation({
    mutationFn: async ({ list, from, to }: { list: OfficeSiteProduct[]; from: number; to: number }) => {
      const order = [...list];
      const [moved] = order.splice(from, 1);
      if (!moved) return;
      order.splice(to, 0, moved);
      for (const [position, row] of order.entries()) {
        if (row.position !== position) await updateSiteProduct(row.id, { position });
      }
    },
    onSettled: refresh,
    onError: failed,
  });

  const list = rows.data ?? [];
  const onSite = new Set(list.map((row) => row.product));
  const addable = (products.data ?? []).filter((product) => !onSite.has(product.id));
  const busy = update.isPending || remove.isPending || move.isPending;

  return (
    <>
      <PageHeader eyebrow={t("admin.groups.site")} title={t("admin.siteProducts.title")}>
        {canEdit && (
          <Button variant="primary" onClick={() => setAdding(true)} disabled={products.isPending}>
            <Icon name="plus" />
            {t("admin.siteProducts.add")}
          </Button>
        )}
      </PageHeader>

      <p className="text-ink-2">{canEdit ? t("admin.siteProducts.intro") : t("admin.siteProducts.readOnly")}</p>

      {rows.isPending ? (
        <p className="text-ink-2">{t("common.loading")}</p>
      ) : rows.isError ? (
        <p role="alert" className="text-bad">
          {t("common.serverUnreachable")}
        </p>
      ) : list.length === 0 ? (
        <EmptyState illustration="mix" title={t("admin.siteProducts.empty")}>
          {t("admin.siteProducts.emptyBody")}
        </EmptyState>
      ) : (
        <Card className="p-2">
          <p className="px-2 pt-1 pb-2 text-[0.85rem] text-ink-2" aria-live="polite">
            {t("admin.siteProducts.count", { count: list.length })}
          </p>
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.siteProducts.columns.product")}</Th>
                <Th>{t("admin.siteProducts.columns.webPrice")}</Th>
                <Th className="max-[900px]:hidden">{t("admin.siteProducts.columns.description")}</Th>
                <Th>{t("admin.siteProducts.columns.status")}</Th>
                {canEdit && <Th>{t("admin.siteProducts.columns.actions")}</Th>}
              </tr>
            </thead>
            <tbody>
              {list.map((row, index) => (
                <SiteProductRow
                  key={`${row.id}-${row.updated_at}`}
                  row={row}
                  dayPrice={dayPrices.get(row.product) ?? null}
                  canEdit={canEdit}
                  busy={busy}
                  first={index === 0}
                  last={index === list.length - 1}
                  onSave={(changes) => update.mutate({ id: row.id, changes })}
                  onMove={(step) => move.mutate({ list, from: index, to: index + step })}
                  onRemove={() => remove.mutate(row)}
                />
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {canEdit && (
        <AddDialog
          open={adding}
          onOpenChange={setAdding}
          products={addable}
          onAdded={async () => {
            setAdding(false);
            toast.success(t("admin.siteProducts.saved"));
            await refresh();
          }}
        />
      )}
    </>
  );
}

function SiteProductRow({
  row,
  dayPrice,
  canEdit,
  busy,
  first,
  last,
  onSave,
  onMove,
  onRemove,
}: {
  row: OfficeSiteProduct;
  dayPrice: string | null;
  canEdit: boolean;
  busy: boolean;
  first: boolean;
  last: boolean;
  onSave: (changes: PatchedSiteProductUpdate) => void;
  onMove: (step: -1 | 1) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const [price, setPrice] = useState(row.web_price ?? "");
  const [description, setDescription] = useState(row.description);
  const parsed = parseWebPrice(price);
  const priceChanged = parsed !== undefined && parsed !== row.web_price;
  const descriptionChanged = description.trim() !== row.description;
  const dirty = priceChanged || descriptionChanged;
  const save = () => {
    if (!dirty || parsed === undefined) return;
    onSave({
      ...(priceChanged ? { web_price: parsed } : {}),
      ...(descriptionChanged ? { description: description.trim() } : {}),
    });
  };

  return (
    <tr className={row.is_published && row.product_active ? undefined : "opacity-70"}>
      <Td>
        <div className="font-semibold">{row.product_name}</div>
        <div className="text-[0.8rem] text-ink-2">
          <span className="num">{row.product_reference}</span> · {row.category_name}
        </div>
      </Td>
      <Td className="min-w-40">
        {canEdit ? (
          <Input
            inputMode="decimal"
            aria-label={t("admin.siteProducts.webPrice")}
            placeholder={t("admin.siteProducts.onRequest")}
            aria-invalid={parsed === undefined ? true : undefined}
            value={price}
            onChange={(event) => setPrice(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") save();
            }}
            className="num w-32"
          />
        ) : (
          <span className="num">{row.web_price ? formatMoney(row.web_price) : t("admin.siteProducts.onRequest")}</span>
        )}
        {dayPrice && (
          <div className="mt-1 text-[0.75rem] text-ink-2">
            {t("admin.siteProducts.dayPrice", { price: formatMoney(dayPrice) })}
          </div>
        )}
      </Td>
      <Td className="max-[900px]:hidden">
        {canEdit ? (
          <Input
            aria-label={t("admin.siteProducts.description")}
            placeholder={t("admin.siteProducts.descriptionHint")}
            maxLength={300}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") save();
            }}
            className="min-w-56"
          />
        ) : (
          row.description || "—"
        )}
      </Td>
      <Td>
        {!row.product_active ? (
          <Pill tone="warn">{t("admin.siteProducts.archived")}</Pill>
        ) : (
          <Pill tone={row.is_published ? "good" : "neutral"}>
            {row.is_published ? t("admin.siteProducts.published") : t("admin.siteProducts.hidden")}
          </Pill>
        )}
      </Td>
      {canEdit && (
        <Td>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button variant="primary" disabled={!dirty || parsed === undefined || busy} onClick={save}>
              {t("admin.siteProducts.save")}
            </Button>
            <Button disabled={busy} onClick={() => onSave({ is_published: !row.is_published })}>
              {row.is_published ? t("admin.siteProducts.hide") : t("admin.siteProducts.show")}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("admin.siteProducts.up")}
              title={t("admin.siteProducts.up")}
              disabled={first || busy}
              onClick={() => onMove(-1)}
            >
              ↑
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("admin.siteProducts.down")}
              title={t("admin.siteProducts.down")}
              disabled={last || busy}
              onClick={() => onMove(1)}
            >
              ↓
            </Button>
            <ConfirmButton
              variant="ghost"
              disabled={busy}
              title={t("admin.siteProducts.removeTitle", { name: row.product_name })}
              rows={[[t("admin.siteProducts.removeBody"), ""]]}
              onConfirm={onRemove}
            >
              <Icon name="trash" />
              <span className="max-[1100px]:sr-only">{t("admin.siteProducts.remove")}</span>
            </ConfirmButton>
          </div>
        </Td>
      )}
    </tr>
  );
}

function AddDialog({
  open,
  onOpenChange,
  products,
  onAdded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  products: Product[];
  onAdded: () => Promise<void>;
}) {
  const { t } = useTranslation();
  const productId = useId();
  const priceId = useId();
  const textId = useId();
  const [product, setProduct] = useState("");
  const [price, setPrice] = useState("");
  const [description, setDescription] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const chosen = products.find((item) => String(item.id) === product);

  const options = products.map<ComboboxOption>((item) => ({
    value: String(item.id),
    label: `${item.name} · ${item.reference}`,
    keywords: [item.name_ar, item.category.name],
  }));
  const reset = () => {
    setProduct("");
    setPrice("");
    setDescription("");
    setErrors({});
  };
  const add = useMutation({
    mutationFn: () => {
      const webPrice = parseWebPrice(price);
      if (webPrice === undefined) throw new TypeError("price");
      return addSiteProduct({ product: Number(product), web_price: webPrice, description: description.trim() });
    },
    onSuccess: async () => {
      reset();
      await onAdded();
    },
    onError: (failure) => {
      if (failure instanceof TypeError) setErrors({ web_price: t("admin.siteProducts.webPriceHint") });
      else setErrors(fieldErrors(failure));
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogTitle>{t("admin.siteProducts.addTitle")}</DialogTitle>
        <DialogDescription>{t("admin.siteProducts.intro")}</DialogDescription>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!product) {
              setErrors({ product: t("admin.siteProducts.noProduct") });
              return;
            }
            add.mutate();
          }}
        >
          <Field label={t("admin.siteProducts.product")} htmlFor={productId} error={errors.product}>
            <Combobox
              id={productId}
              placeholder={t("admin.siteProducts.productHint")}
              value={product}
              onValueChange={(value) => {
                setProduct(value);
                const picked = products.find((item) => String(item.id) === value);
                if (picked?.current_price && price === "") setPrice(picked.current_price);
              }}
              options={options}
              empty={t("admin.siteProducts.noProduct")}
            />
          </Field>
          <Field label={t("admin.siteProducts.webPrice")} htmlFor={priceId} error={errors.web_price}>
            <Input
              id={priceId}
              inputMode="decimal"
              placeholder={t("admin.siteProducts.webPriceHint")}
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              className="num"
            />
            {chosen?.current_price && (
              <span className="text-[0.78rem] text-ink-2">
                {t("admin.siteProducts.dayPrice", { price: formatMoney(chosen.current_price) })}
              </span>
            )}
          </Field>
          <Field label={t("admin.siteProducts.description")} htmlFor={textId} error={errors.description}>
            <Input
              id={textId}
              maxLength={300}
              placeholder={t("admin.siteProducts.descriptionHint")}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </Field>
          <DialogFooter>
            <Button onClick={() => onOpenChange(false)}>{t("admin.siteProducts.cancel")}</Button>
            <Button type="submit" variant="primary" disabled={add.isPending}>
              {t("admin.siteProducts.add")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
