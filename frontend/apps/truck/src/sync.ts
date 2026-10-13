import {
  addMyExpense,
  ApiError,
  collectMyBoxes,
  collectMyPayment,
  createSale,
  reportMyLoss,
  reportSyncProblem,
} from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { listQueue, markRefused, markReported, type QueuedItem, removeQueued } from "./queue";

// Every text the server put in an error answer, so the driver reads why a sale was refused.
function messagesOf(body: unknown): string[] {
  if (typeof body === "string") return [body];
  if (Array.isArray(body)) return body.flatMap(messagesOf);
  if (typeof body === "object" && body !== null) return Object.values(body).flatMap(messagesOf);
  return [];
}

let sending = false;

/** Tell the office a send was refused (once, kept until it has worked): it is never lost on the phone alone. */
async function tellOffice(item: QueuedItem): Promise<void> {
  try {
    await reportSyncProblem({ kind: item.kind, what: item.label, reason: item.error, client_uuid: item.uuid });
    await markReported(item);
  } catch {
    // No connection or no login right now: it is reported on a later run.
  }
}

function sendItem(item: QueuedItem): Promise<unknown> {
  if (item.kind === "sale") return createSale(item.data);
  if (item.kind === "expense") return addMyExpense(item.data);
  if (item.kind === "payment") return collectMyPayment(item.data);
  if (item.kind === "pickup") return collectMyBoxes(item.data);
  return reportMyLoss(item.data);
}

/** Send what waits one by one, oldest first. Stops at the first sign of no connection or no login. */
export async function sendWaiting(queryClient: QueryClient): Promise<void> {
  if (sending || !navigator.onLine) return;
  sending = true;
  let sent = false;
  try {
    for (const item of await listQueue()) {
      if (item.status === "refused") {
        if (item.reported !== true) await tellOffice(item);
        continue;
      }
      try {
        await sendItem(item);
        await removeQueued(item.uuid);
        sent = true;
      } catch (failure) {
        // The connection dropped or the session ended: keep everything and try again later.
        if (!(failure instanceof ApiError) || failure.status === 401) break;
        const refused = {
          ...item,
          status: "refused" as const,
          error: messagesOf(failure.body).join(" ") || failure.message,
        };
        await markRefused(item, refused.error);
        await tellOffice(refused);
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
