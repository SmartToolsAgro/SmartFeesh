import { useListMyFieldPurchases } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Button, Card } from "@frutti/ui";
import { Link } from "react-router";

import { markDecisionRead, usePurchaseDecisions } from "./purchaseWatch";

/** The office validated or refused a purchase: said on every screen until the driver read it (D-158). Asked again
 * every minute while the app is open, for a driver who buys. */
export function PurchaseNotice({ enabled }: { enabled: boolean }) {
  const { t } = useTranslation();
  const purchases = useListMyFieldPurchases({ query: { enabled, refetchInterval: 60_000, retry: false } });
  const decisions = usePurchaseDecisions(enabled ? purchases.data : undefined);
  if (decisions.length === 0) return null;
  return (
    <Card role="alert" className="space-y-3 border-warn">
      <ul className="space-y-3">
        {decisions.map((purchase) => (
          <li key={purchase.id} className="space-y-1">
            <p className={purchase.status === "refused" ? "font-semibold text-bad" : "font-semibold text-good"}>
              {t(purchase.status === "refused" ? "truck.purchase.noticeRefused" : "truck.purchase.noticeValidated", {
                number: purchase.number,
              })}
            </p>
            {purchase.office_note ? <p>{t("truck.purchase.officeNote", { note: purchase.office_note })}</p> : null}
            <div className="flex gap-2">
              <Button onClick={() => markDecisionRead(purchase.id)}>{t("truck.purchase.ok")}</Button>
              <Button asChild variant="ghost">
                <Link to="/achats" onClick={() => markDecisionRead(purchase.id)}>
                  {t("truck.purchase.mine")}
                </Link>
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
