import { useTranslation } from "@frutti/i18n";
import { useQueryClient } from "@tanstack/react-query";

import { useQueue } from "./queue";
import { useSalesSync } from "./sync";

/** Always visible when something waits: how many things are not sent yet, and any the server refused. */
export function SyncStatus() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  useSalesSync(queryClient);
  const queue = useQueue();
  const waiting = queue.filter((item) => item.status === "pending");
  const refused = queue.filter((item) => item.status === "refused");
  if (queue.length === 0) return null;
  return (
    <div className="mb-4 space-y-2" role="status">
      {waiting.length > 0 && (
        <p className="rounded-control bg-sea-soft px-3 py-2 text-sea">
          {t("truck.sync.waiting", { count: waiting.length })}
        </p>
      )}
      {refused.map((item) => (
        <p key={item.uuid} className="rounded-control bg-bad-soft px-3 py-2 text-bad">
          {t("truck.sync.refused", { what: item.label, reason: item.error })}
        </p>
      ))}
    </div>
  );
}
