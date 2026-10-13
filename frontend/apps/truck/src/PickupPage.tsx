import { ApiError, type CustomerChoice, useCollectMyBoxes } from "@frutti/api";
import { useSession } from "@frutti/auth";
import { useTranslation } from "@frutti/i18n";
import { Button, Card, EmptyState } from "@frutti/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { BoxCountInputs } from "./BoxCountInputs";
import { boxCountsOf, hasBoxes, type BoxInputs, NO_BOXES } from "./boxes";
import { messagesOf } from "./messages";
import { useOnline } from "./offline";
import { PickCustomer } from "./SalePage";

// "Reprise de caisses": the boxes a client hands back to the truck today. Online only for now (P1-T14d).
export function PickupPage() {
  const { t } = useTranslation();
  const session = useSession();
  const queryClient = useQueryClient();
  const online = useOnline();
  const truck = session.data?.truck ?? null;
  const [customer, setCustomer] = useState<CustomerChoice | null>(null);
  const [inputs, setInputs] = useState<BoxInputs>(NO_BOXES);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const collect = useCollectMyBoxes({
    mutation: {
      onSuccess: () => {
        setError("");
        setInputs(NO_BOXES);
        setCustomer(null);
        setSaved(true);
        void queryClient.invalidateQueries();
      },
      onError: (failure) => {
        setError(
          failure instanceof ApiError
            ? messagesOf(failure.body).join(" ") || t("truck.boxes.pickupFailed")
            : t("truck.boxes.needConnection"),
        );
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
  if (saved && customer === null) {
    return (
      <div className="space-y-4">
        <Card className="space-y-3">
          <p className="text-xl font-bold">{t("truck.boxes.pickupSaved")}</p>
        </Card>
        <Button size="lg" variant="primary" className="py-4 text-lg" onClick={() => setSaved(false)}>
          {t("truck.boxes.pickupAnother")}
        </Button>
        <Button asChild size="lg" className="py-4 text-lg">
          <Link to="/">{t("truck.boxes.back")}</Link>
        </Button>
      </div>
    );
  }
  if (customer === null) return <PickCustomer onPick={setCustomer} />;

  const counts = boxCountsOf(inputs);
  const canSave = counts !== null && hasBoxes(counts) && online && !collect.isPending;

  return (
    <div className="space-y-4">
      <Card className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-ink-2">{t("truck.sale.customer")}</p>
          <p className="text-xl font-bold">{customer.name}</p>
        </div>
        <Button onClick={() => setCustomer(null)}>{t("truck.sale.change")}</Button>
      </Card>
      <Card className="space-y-3">
        <h2>{t("truck.boxes.pickupTitle")}</h2>
        <BoxCountInputs inputs={inputs} onChange={setInputs} />
        {counts === null ? <p className="text-bad">{t("truck.boxes.invalidCount")}</p> : null}
        {counts !== null && !hasBoxes(counts) ? <p className="text-ink-2">{t("truck.boxes.pickupNone")}</p> : null}
        {online ? null : <p className="text-bad">{t("truck.boxes.needConnection")}</p>}
        {error === "" ? null : <p className="text-bad">{error}</p>}
        <Button
          size="lg"
          variant="primary"
          className="py-4 text-lg"
          disabled={!canSave}
          onClick={() => counts !== null && collect.mutate({ data: { customer: customer.id, boxes: counts } })}
        >
          {t("truck.boxes.pickupSave")}
        </Button>
      </Card>
    </div>
  );
}
