import { useListPartnerships } from "@frutti/api";
import type { Session } from "@frutti/auth";
import { useMemo } from "react";

import { canReadResults } from "./shared";

/** The partners of each product's lots still being sold: product id → partner names. `undefined` until it loads,
 * and for a role that may not read partnerships (the server answers 403 to them): show no partner marks then. */
export function usePartnerProducts(session: Session): Map<string, string[]> | undefined {
  const allowed = canReadResults(session);
  const listed = useListPartnerships({ status: "open", limit: 200 }, { query: { enabled: allowed } });
  return useMemo(() => {
    if (!allowed || !listed.data) return undefined;
    const byProduct = new Map<string, string[]>();
    for (const partnership of listed.data.results) {
      const key = String(partnership.batch.product_id);
      const names = byProduct.get(key) ?? [];
      if (!names.includes(partnership.partner.name)) byProduct.set(key, [...names, partnership.partner.name]);
    }
    return byProduct;
  }, [allowed, listed.data]);
}
