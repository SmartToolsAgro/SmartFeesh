import type { StockMovement } from "@frutti/api";
import { formatDateTime, formatQuantity, useTranslation } from "@frutti/i18n";
import { Pill, Table, Td, Th } from "@frutti/ui";
import { Link } from "react-router";

import { MOVEMENT_TONES } from "./shared";

/** Ledger rows like the prototype's "Derniers mouvements": when, what, product · batch, from → to, kg, who. */
export function MovementsTable({ movements }: { movements: StockMovement[] }) {
  const { t } = useTranslation();
  const place = (location: StockMovement["from_location"]) => location?.name ?? t("admin.stock.outside");
  return (
    <Table>
      <thead>
        <tr>
          <Th>{t("admin.stock.movements.columns.when")}</Th>
          <Th>{t("admin.stock.movements.columns.kind")}</Th>
          <Th>{t("admin.stock.movements.columns.product")}</Th>
          <Th className="max-[720px]:hidden">{t("admin.stock.movements.columns.route")}</Th>
          <Th numeric>{t("admin.stock.movements.columns.quantity")}</Th>
          <Th className="max-[720px]:hidden">{t("admin.stock.movements.columns.by")}</Th>
        </tr>
      </thead>
      <tbody>
        {movements.map((movement) => (
          <tr key={movement.id}>
            <Td className="num whitespace-nowrap">{formatDateTime(movement.occurred_at)}</Td>
            <Td>
              <Pill tone={MOVEMENT_TONES[movement.kind]}>{t(`admin.stock.movements.kinds.${movement.kind}`)}</Pill>
            </Td>
            <Td>
              <Link to={`/stock/produits/${movement.product.id}`} className="font-semibold hover:underline">
                {movement.product.name}
              </Link>
              {" · "}
              <Link to={`/stock/lots/${movement.batch_id}`} className="num text-sea hover:underline">
                {movement.batch_number}
              </Link>
              {movement.reason && <span className="block text-[0.8rem] text-ink-2">{movement.reason}</span>}
            </Td>
            <Td className="max-[720px]:hidden">
              {t("admin.stock.movements.route", {
                from: place(movement.from_location),
                to: place(movement.to_location),
              })}
            </Td>
            <Td numeric className="whitespace-nowrap">
              {formatQuantity(movement.quantity)}
            </Td>
            <Td className="max-[720px]:hidden">{movement.user_name || t("admin.stock.none")}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
