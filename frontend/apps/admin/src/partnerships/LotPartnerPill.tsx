import { useListPartnerships } from "@frutti/api";
import { useTranslation } from "@frutti/i18n";
import { Pill } from "@frutti/ui";

import { STATUS_TONE } from "./shared";

/** At the top of a lot: who the partner is, or that the lot is the owner's alone. Shares its query with
 * the partnership section below, so it costs no extra request. */
export function LotPartnerPill({ batchId }: { batchId: number }) {
  const { t } = useTranslation();
  const listed = useListPartnerships({ batch: batchId });
  if (!listed.data) return null;
  const partnership = listed.data.results[0];
  if (!partnership) return <Pill tone="neutral">{t("admin.partnerships.section.pillNone")}</Pill>;
  return (
    <>
      <Pill tone={STATUS_TONE[partnership.status]}>
        {t("admin.partnerships.section.pill", { name: partnership.partner.name })}
      </Pill>
      {partnership.terms_pending && <Pill tone="warn">{t("admin.partnerships.section.pending")}</Pill>}
    </>
  );
}
