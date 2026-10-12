import { useListPartnerships } from "@frutti/api";
import type { Session } from "@frutti/auth";

import { canReadResults } from "./shared";

/** Who is a partner right now (D-060): a supplier is a partner while they have a partnership on an open lot.
 * Maps the supplier's id to their number of open partnership lots. `undefined` while loading, or when the
 * role may not read partnerships (the server answers 403 to them): show no partner marks then. */
export function usePartnerSuppliers(session: Session): Map<number, number> | undefined {
  const allowed = canReadResults(session);
  const partnerships = useListPartnerships({ status: "open", limit: 200 }, { query: { enabled: allowed } });
  if (!allowed || !partnerships.data) return undefined;
  const lots = new Map<number, number>();
  for (const row of partnerships.data.results) lots.set(row.partner.id, (lots.get(row.partner.id) ?? 0) + 1);
  return lots;
}
