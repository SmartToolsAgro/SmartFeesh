import { ApiError, createSale } from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { listQueue, markRefused, removeQueuedSale } from "./salesQueue";

// Every text the server put in an error answer, so the driver reads why a sale was refused.
function messagesOf(body: unknown): string[] {
  if (typeof body === "string") return [body];
  if (Array.isArray(body)) return body.flatMap(messagesOf);
  if (typeof body === "object" && body !== null) return Object.values(body).flatMap(messagesOf);
  return [];
}

let sending = false;

/** Send the waiting sales one by one, oldest first. Stops at the first sign of no connection or no login. */
export async function sendWaitingSales(queryClient: QueryClient): Promise<void> {
  if (sending || !navigator.onLine) return;
  sending = true;
  let sent = false;
  try {
    for (const sale of await listQueue()) {
      if (sale.status !== "pending") continue;
      try {
        await createSale(sale.data);
        await removeQueuedSale(sale.uuid);
        sent = true;
      } catch (failure) {
        // The connection dropped or the session ended: keep everything and try again later.
        if (!(failure instanceof ApiError) || failure.status === 401) break;
        await markRefused(sale, messagesOf(failure.body).join(" ") || failure.message);
      }
    }
  } finally {
    sending = false;
  }
  if (sent) await queryClient.invalidateQueries();
}

/** Tries to send at start, when the connection comes back, and every half minute while sales wait. */
export function useSalesSync(queryClient: QueryClient): void {
  useEffect(() => {
    const run = () => void sendWaitingSales(queryClient);
    run();
    window.addEventListener("online", run);
    const timer = window.setInterval(run, 30_000);
    return () => {
      window.removeEventListener("online", run);
      window.clearInterval(timer);
    };
  }, [queryClient]);
}
