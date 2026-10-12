import { addMyExpense, ApiError, createSale, reportMyLoss } from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { listQueue, markRefused, type QueuedItem, removeQueued } from "./queue";

// Every text the server put in an error answer, so the driver reads why a sale was refused.
function messagesOf(body: unknown): string[] {
  if (typeof body === "string") return [body];
  if (Array.isArray(body)) return body.flatMap(messagesOf);
  if (typeof body === "object" && body !== null) return Object.values(body).flatMap(messagesOf);
  return [];
}

let sending = false;

function sendItem(item: QueuedItem): Promise<unknown> {
  if (item.kind === "sale") return createSale(item.data);
  if (item.kind === "expense") return addMyExpense(item.data);
  return reportMyLoss(item.data);
}

/** Send what waits one by one, oldest first. Stops at the first sign of no connection or no login. */
export async function sendWaiting(queryClient: QueryClient): Promise<void> {
  if (sending || !navigator.onLine) return;
  sending = true;
  let sent = false;
  try {
    for (const item of await listQueue()) {
      if (item.status !== "pending") continue;
      try {
        await sendItem(item);
        await removeQueued(item.uuid);
        sent = true;
      } catch (failure) {
        // The connection dropped or the session ended: keep everything and try again later.
        if (!(failure instanceof ApiError) || failure.status === 401) break;
        await markRefused(item, messagesOf(failure.body).join(" ") || failure.message);
      }
    }
  } finally {
    sending = false;
  }
  if (sent) await queryClient.invalidateQueries();
}

/** Tries to send at start, when the connection comes back, and every half minute while something waits. */
export function useSalesSync(queryClient: QueryClient): void {
  useEffect(() => {
    const run = () => void sendWaiting(queryClient);
    run();
    window.addEventListener("online", run);
    const timer = window.setInterval(run, 30_000);
    return () => {
      window.removeEventListener("online", run);
      window.clearInterval(timer);
    };
  }, [queryClient]);
}
