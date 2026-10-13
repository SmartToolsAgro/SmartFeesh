import { ApiError, collectMyBoxes, type CustomerChoice, type MyBoxPickupWrite } from "@frutti/api";
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
import { sendOrKeep } from "./sendOrKeep";
import { PickCustomer } from "./SalePage";
import { newUuid } from "./uuid";

// "Reprise de caisses": the boxes a client hands back to the truck today (P1-T14d). Offline, the pickup is kept
// on the phone with its own client_uuid and sent when the network is back (P1-T14e, decision 3).
export function PickupPage() {
  const { t } = useTranslation();
  const session = useSession();
  const queryClient = useQueryClient();
  const online = useOnline();
  const truck = session.data?.truck ?? null;
  const [customer, setCustomer] = useState<CustomerChoice | null>(null);
  const [inputs, setInputs] = useState<BoxInputs>(NO_BOXES);
  const [outcome, setOutcome] = useState<"sent" | "kept" | null>(null);
  const [sending, setSending] = useState(false);
  const [uuid, setUuid] = useState(newUuid);
  const [error, setError] = useState("");

  if (truck === null) {
    return (
      <EmptyState illustration="truck" title={t("truck.day.noTruck")}>
        {t("truck.sale.needTruck")}
      </EmptyState>
    );
  }
  if (outcome !== null && customer === null) {
    return (
      <div className="space-y-4">
        <Card className="space-y-3">
          <p className="text-xl font-bold">
            {outcome === "kept" ? t("truck.boxes.pickupKept") : t("truck.boxes.pickupSaved")}
          </p>
        </Card>
        <Button size="lg" variant="primary" className="py-4 text-lg" onClick={() => setOutcome(null)}>
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
  const canSave = counts !== null && hasBoxes(counts) && !sending;

  const save = async () => {
    if (counts === null || !hasBoxes(counts)) return;
    const data: MyBoxPickupWrite = { customer: customer.id, boxes: counts, client_uuid: uuid };
    setError("");
    setSending(true);
    try {
      const { kept } = await sendOrKeep(
        {
          kind: "pickup",
          uuid,
          createdAt: new Date().toISOString(),
          label: customer.name,
          data,
          status: "pending",
          error: "",
        },
        () => collectMyBoxes(data),
      );
      setOutcome(kept ? "kept" : "sent");
      setInputs(NO_BOXES);
      setCustomer(null);
      setUuid(newUuid());
      void queryClient.invalidateQueries();
    } catch (failure) {
      // The server refused it (for instance too few boxes at the client): nothing is kept, the driver corrects it.
      setError(
        failure instanceof ApiError
          ? messagesOf(failure.body).join(" ") || t("truck.boxes.pickupFailed")
          : t("truck.boxes.pickupFailed"),
      );
    } finally {
      setSending(false);
    }
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
      <Card className="space-y-3">
        <h2>{t("truck.boxes.pickupTitle")}</h2>
        <BoxCountInputs inputs={inputs} onChange={setInputs} />
        {counts === null ? <p className="text-bad">{t("truck.boxes.invalidCount")}</p> : null}
        {counts !== null && !hasBoxes(counts) ? <p className="text-ink-2">{t("truck.boxes.pickupNone")}</p> : null}
        {online ? null : <p className="text-ink-2">{t("truck.boxes.pickupKept")}</p>}
        {error === "" ? null : <p className="text-bad">{error}</p>}
        <Button size="lg" variant="primary" className="py-4 text-lg" disabled={!canSave} onClick={() => void save()}>
          {t("truck.boxes.pickupSave")}
        </Button>
      </Card>
    </div>
  );
}
