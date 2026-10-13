import type { MyBoxPickupWrite, RoadExpenseWrite, RoadLossWrite, RoadPaymentWrite, SaleWrite } from "@frutti/api";
import { useEffect, useState } from "react";

// What the phone could not send yet (P3-T07b and T07c, D-097). They live in IndexedDB, so they survive closing the
// app or restarting the phone, until the server has taken them.

interface Waiting {
  /** The item's `client_uuid`: the server never makes two records from the same one. */
  uuid: string;
  createdAt: string;
  /** What the driver would call it: the customer, the category, the product. */
  label: string;
  /** "pending": waiting for a connection. "refused": the server said no; it stays until someone looks at it. */
  status: "pending" | "refused";
  error: string;
  /** The office has been told about a refusal (P3-T07d). */
  reported?: boolean;
}

export interface QueuedSale extends Waiting {
  kind: "sale";
  data: SaleWrite;
  /** What the screen showed when the sale was made, for the receipt on the phone. */
  estimate: {
    lines: { name: string; kilos: string; amount: string }[];
    total: string;
    paid: string;
  };
}

export interface QueuedExpense extends Waiting {
  kind: "expense";
  /** The receipt photo travels with it (IndexedDB keeps files). */
  data: RoadExpenseWrite;
}

export interface QueuedLoss extends Waiting {
  kind: "loss";
  data: RoadLossWrite;
}

export interface QueuedPayment extends Waiting {
  kind: "payment";
  data: RoadPaymentWrite;
}

/** Boxes a client hands back to the truck (P1-T14e): the `client_uuid` in the data makes a retry post once. */
export interface QueuedPickup extends Waiting {
  kind: "pickup";
  data: MyBoxPickupWrite;
}

export type QueuedItem = QueuedSale | QueuedExpense | QueuedLoss | QueuedPayment | QueuedPickup;

const DATABASE = "frutti-truck";
const STORE = "sales";
const listeners = new Set<() => void>();

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "uuid" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB"));
  });
}

async function run<T>(mode: IDBTransactionMode, work: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const database = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = work(database.transaction(STORE, mode).objectStore(STORE));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error ?? new Error("IndexedDB"));
    });
  } finally {
    database.close();
  }
}

function changed(): void {
  listeners.forEach((listener) => listener());
}

/** Oldest first, the order they were made in. */
export async function listQueue(): Promise<QueuedItem[]> {
  const rows = await run("readonly", (store) => store.getAll() as IDBRequest<QueuedItem[]>);
  return rows.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export async function enqueue(item: QueuedItem): Promise<void> {
  await run("readwrite", (store) => store.put(item));
  changed();
}

export async function removeQueued(uuid: string): Promise<void> {
  await run("readwrite", (store) => store.delete(uuid));
  changed();
}

export async function markReported(item: QueuedItem): Promise<void> {
  await run("readwrite", (store) => store.put({ ...item, reported: true }));
  changed();
}

export async function markRefused(item: QueuedItem, error: string): Promise<void> {
  await run("readwrite", (store) => store.put({ ...item, status: "refused", error }));
  changed();
}

/** The queue, kept up to date on screen. */
export function useQueue(): QueuedItem[] {
  const [queue, setQueue] = useState<QueuedItem[]>([]);
  useEffect(() => {
    let alive = true;
    const refresh = () => {
      listQueue()
        .then((rows) => alive && setQueue(rows))
        .catch(() => undefined);
    };
    refresh();
    listeners.add(refresh);
    return () => {
      alive = false;
      listeners.delete(refresh);
    };
  }, []);
  return queue;
}

/** Kilos per product already promised by waiting sales and losses: they are no longer in the truck. */
export function pendingKilos(queue: QueuedItem[]): Record<number, number> {
  const kilos: Record<number, number> = {};
  for (const item of queue) {
    if (item.status !== "pending") continue;
    if (item.kind === "sale") {
      for (const line of item.data.lines) kilos[line.product] = (kilos[line.product] ?? 0) + Number(line.quantity);
    } else if (item.kind === "loss") {
      kilos[item.data.product] = (kilos[item.data.product] ?? 0) + Number(item.data.quantity);
    }
  }
  return kilos;
}
