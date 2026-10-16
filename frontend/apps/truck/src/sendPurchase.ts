import {
  addMyFieldPurchasePaper,
  type MyFieldPurchase,
  type MyFieldPurchaseCreate,
  sendMyFieldPurchase,
} from "@frutti/api";

/**
 * Send a purchase at the port, then the photo of the supplier's paper when there is one (D-159). Sent again after
 * a lost answer or a failed photo, the same `client_uuid` gives back the purchase already saved, and the photo goes
 * on it: one purchase, one photo.
 */
export async function sendPurchase(
  data: MyFieldPurchaseCreate,
  paper: File | undefined,
  options?: RequestInit,
): Promise<MyFieldPurchase> {
  const saved = await sendMyFieldPurchase(data, options);
  if (paper === undefined) return saved;
  return addMyFieldPurchasePaper(saved.id, { paper }, options);
}
