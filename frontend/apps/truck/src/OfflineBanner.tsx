import { useTranslation } from "@frutti/i18n";

import { useOnline } from "./offline";

/** One calm line at the top of the screens while there is no signal. */
export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useOnline();
  if (online) return null;
  return (
    <p role="status" className="mb-4 rounded-control bg-warn-soft px-3 py-2 text-warn">
      {t("truck.offline.banner")}
    </p>
  );
}
