import {
  addMyExpense,
  ApiError,
  collectMyBoxes,
  collectMyPayment,
  createSale,
  deliverMyDelivery,
  notDeliveredMyDelivery,
  reportMyLoss,
  reportSyncProblem,
} from "@frutti/api";
import type { QueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { listQueue, madeAtOf, markRefused, markReported, type QueuedItem, removeQueued } from "./queue";
import { sendPurchase } from "./sendPurchase";

// Every text the server put in an error answer, so the driver reads why a sale was refused.
function messagesOf(body: unknown): string[] {
  if (typeof body === "string") return [body];
  if (Array.isArray(body)) return body.flatMap(messagesOf);
  if (typeof body === "object" && body !== null) return Object.values(body).flatMap(messagesOf);
  return [];
}

/** A send that gets no answer in this time counts as no connection (a weak signal can hang a request for minutes). */
export const SEND_TIMEOUT_MS = 25_000;

/** Answers that mean "try again later", not "the server refused this item": the item stays pending. */
const RETRY_LATER = new Set([408, 429, 502, 503, 504]);

/**
 * Why the last run could not send everything: "offline" (no connection or no answer), "session" (the login
 * ended, sign in again) or "server" (busy or restarting). null when the last run sent all it had.
 */
export type SyncProblem = "offline" | "session" | "server" | null;

let problem: SyncProblem = null;
const problemListeners = new Set<() => void>();

function setProblem(next: SyncProblem): void {
  if (next === problem) return;
  problem = next;
  problemListeners.forEach((listener) => listener());
}

export function getSyncProblem(): SyncProblem {
  return problem;
}

/** The last sync problem, kept up to date on screen. */
export function useSyncProblem(): SyncProblem {
  const [current, setCurrent] = useState<SyncProblem>(problem);
  useEffect(() => {
    const update = () => setCurrent(problem);
    problemListeners.add(update);
    update();
    return () => {
      problemListeners.delete(update);
    };
  }, []);
  return current;
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

function sendItem(item: QueuedItem, options: RequestInit): Promise<unknown> {
  // A sale goes with the time it was made, not the time it is sent (D-133): the server dates it from that.
  if (item.kind === "sale") return createSale({ ...item.data, sold_at: madeAtOf(item) }, options);
  // An expense, a payment, boxes or a loss keep the time they were entered on the phone too, so the day they
  // belong to is the day they happened (P3-T07c, D-133).
  const madeAt = item.createdAt;
  if (item.kind === "expense") return addMyExpense({ ...item.data, made_at: madeAt }, options);
  if (item.kind === "payment") return collectMyPayment({ ...item.data, made_at: madeAt }, options);
  if (item.kind === "pickup") return collectMyBoxes({ ...item.data, made_at: madeAt }, options);
  if (item.kind === "purchase") return sendPurchase({ ...item.data, made_at: madeAt }, item.paper, options);
  if (item.kind === "delivery") return deliverMyDelivery(item.saleId, item.data, options);
  if (item.kind === "not_delivered") return notDeliveredMyDelivery(item.saleId, item.data, options);
  return reportMyLoss({ ...item.data, made_at: madeAt }, options);
}

/** One send, given up after SEND_TIMEOUT_MS: the request is aborted and the timeout reads as "no connection". */
async function sendWithTimeout(item: QueuedItem): Promise<unknown> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new TypeError("timeout"));
    }, SEND_TIMEOUT_MS);
  });
  try {
    return await Promise.race([sendItem(item, { signal: controller.signal }), timeout]);
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Send what waits one by one, oldest first. Stops at the first sign of no connection, no login or a busy server,
 * and says which one it was (see `useSyncProblem`).
 */
export async function sendWaiting(queryClient: QueryClient): Promise<void> {
  if (sending) return;
  if (!navigator.onLine) {
    setProblem("offline");
    return;
  }
  sending = true;
  let sent = false;
  let stopped: SyncProblem = null;
  try {
    for (const item of await listQueue()) {
      if (item.status === "refused") {
        if (item.reported !== true) await tellOffice(item);
        continue;
      }
      try {
        await sendWithTimeout(item);
        await removeQueued(item.uuid);
        sent = true;
      } catch (failure) {
        if (!(failure instanceof ApiError)) {
          // The connection dropped or did not answer: keep everything and try again later.
          stopped = "offline";
          break;
        }
        if (failure.status === 401) {
          stopped = "session";
          break;
        }
        if (RETRY_LATER.has(failure.status)) {
          stopped = "server";
          break;
        }
        const error = messagesOf(failure.body).join(" ") || failure.message;
        await markRefused(item, error);
        await tellOffice({ ...item, status: "refused", error });
      }
    }
  } finally {
    sending = false;
  }
  setProblem(stopped);
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
