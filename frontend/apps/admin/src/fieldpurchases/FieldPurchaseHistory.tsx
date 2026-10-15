import type { FieldPurchaseRevision, PaymentMethodEnum, PaymentTermsEnum, RevisionChange } from "@frutti/api";
import { formatDate, formatDateTime, formatMoney, formatQuantity, useTranslation } from "@frutti/i18n";
import { Card, CardTitle, Pill } from "@frutti/ui";

import { isHistoryField, shapeOf } from "./shared";

const TONE = { submitted: "sea", edited: "neutral", validated: "good", refused: "bad" } as const;

/** Every saved version of a purchase, newest first, each with what it changed against the one before. */
export function FieldPurchaseHistory({ revisions }: { revisions: readonly FieldPurchaseRevision[] }) {
  const { t } = useTranslation();

  const label = (field: string) => (isHistoryField(field) ? t(`admin.fieldPurchases.history.fields.${field}`) : field);

  /** A value as people read it: kg, DT, a date, a deal or a payment mode by the field it belongs to. */
  const shown = (field: string, value: string | null) => {
    if (value === null) return t("admin.fieldPurchases.history.empty");
    if (field === "declared_quantity" || field === "received_quantity") return formatQuantity(value);
    if (field === "unit_cost" || field === "amount") return formatMoney(value);
    if (field === "bought_on" || field === "cash_on") return formatDate(value);
    if (field === "terms") return t(`admin.fieldPurchases.termsChoice.${value as PaymentTermsEnum}`);
    if (field === "method") return t(`admin.supplierPayments.method.${value as PaymentMethodEnum}`);
    return value;
  };

  const describe = (change: RevisionChange) => {
    const shape = shapeOf(change);
    if (shape.kind === "added" || shape.kind === "removed") {
      const raw = shape.kind === "added" ? change.after : change.before;
      // A payment row is named by its amount, a line by its product.
      const name = shape.row === "payment" ? shown("amount", raw) : (raw ?? "");
      const key =
        shape.row === "line"
          ? shape.kind === "added"
            ? "lineAdded"
            : "lineRemoved"
          : shape.kind === "added"
            ? "paymentAdded"
            : "paymentRemoved";
      return t(`admin.fieldPurchases.history.${key}`, { number: shape.number, name });
    }
    const what =
      shape.kind === "row"
        ? t(`admin.fieldPurchases.history.${shape.row}`, { number: shape.number, field: label(shape.field) })
        : label(shape.field);
    return `${what} : ${shown(shape.field, change.before)} → ${shown(shape.field, change.after)}`;
  };

  return (
    <Card>
      <CardTitle>{t("admin.fieldPurchases.history.title")}</CardTitle>
      <ol className="flex flex-col gap-4">
        {[...revisions].reverse().map((revision) => (
          <li key={revision.number} className="flex flex-col gap-1 border-s-2 border-line ps-3">
            <div className="flex flex-wrap items-center gap-2">
              <b>{t("admin.fieldPurchases.history.version", { number: revision.number })}</b>
              <Pill tone={TONE[revision.action]}>{t(`admin.fieldPurchases.history.action.${revision.action}`)}</Pill>
              <span className="num text-[0.85rem] text-ink-2">{formatDateTime(revision.created_at)}</span>
              {revision.created_by && (
                <span className="text-[0.85rem] text-ink-2">
                  {t("admin.fieldPurchases.history.by", { name: revision.created_by })}
                </span>
              )}
            </div>
            {revision.note && <p className="whitespace-pre-line italic">« {revision.note} »</p>}
            {revision.changes.length > 0 ? (
              <ul className="flex flex-col gap-0.5 text-[0.9rem]">
                {revision.changes.map((change, index) => (
                  <li key={index}>{describe(change)}</li>
                ))}
              </ul>
            ) : (
              revision.action === "edited" && (
                <p className="text-[0.85rem] text-ink-2">{t("admin.fieldPurchases.history.noChange")}</p>
              )
            )}
            {revision.action === "submitted" && revision.number === 1 && (
              <p className="text-[0.85rem] text-ink-2">{t("admin.fieldPurchases.history.firstVersion")}</p>
            )}
          </li>
        ))}
      </ol>
    </Card>
  );
}
