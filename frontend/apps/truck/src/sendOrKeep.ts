import { ApiError } from "@frutti/api";

import { enqueue, type QueuedItem } from "./queue";

/**
 * Send now; with no connection, keep the item on the phone to be sent later. A refusal by the server (an
 * `ApiError`) is not kept: it is thrown so the screen can tell the driver why.
 */
export async function sendOrKeep<T>(item: QueuedItem, send: () => Promise<T>): Promise<{ kept: boolean; result?: T }> {
  try {
    if (!navigator.onLine) throw new TypeError("offline");
    return { kept: false, result: await send() };
  } catch (failure) {
    if (failure instanceof ApiError) throw failure;
    await enqueue(item);
    return { kept: true };
  }
}
