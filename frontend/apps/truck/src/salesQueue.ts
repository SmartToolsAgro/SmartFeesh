import type { SaleWrite } from "@frutti/api";
import { useEffect, useState } from "react";

// The sales the phone could not send yet (P3-T07b, D-097). They live in IndexedDB, so they survive closing the
// app or restarting the phone, until the server has taken them.

export interface QueuedSale {
  /** The sale's `client_uuid`: the server never makes two sales from the same one. */
  uuid: string;
  createdAt: string;
  customerName: string;
  data: SaleWrite;
  /** What the screen showed when the sale was made, for the receipt on the phone. */
  estimate: {
    lines: { name: string; kilos: string; amount: string }[];
    total: string;
    paid: string;
  };
  /** "pending": waiting for a connection. "refused": the server said no; it stays until someone looks at it. */
  status: "pending" | "refused";
  error: string;
}

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
export async function listQueue(): Promise<QueuedSale[]> {
  const rows = await run("readonly", (store) => store.getAll() as IDBRequest<QueuedSale[]>);
  return rows.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export async function enqueueSale(sale: QueuedSale): Promise<void> {
  await run("readwrite", (store) => store.put(sale));
  changed();
}

export async function removeQueuedSale(uuid: string): Promise<void> {
  await run("readwrite", (store) => store.delete(uuid));
  changed();
}

export async function markRefused(sale: QueuedSale, error: string): Promise<void> {
  await run("readwrite", (store) => store.put({ ...sale, status: "refused", error }));
  changed();
}

/** The queue, kept up to date on screen. */
export function useQueue(): QueuedSale[] {
  const [queue, setQueue] = useState<QueuedSale[]>([]);
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

/** Kilos per product already promised by waiting sales: they are no longer in the truck for the next sale. */
export function pendingKilos(queue: QueuedSale[]): Record<number, number> {
  const kilos: Record<number, number> = {};
  for (const sale of queue) {
    if (sale.status !== "pending") continue;
    for (const line of sale.data.lines) {
      kilos[line.product] = (kilos[line.product] ?? 0) + Number(line.quantity);
    }
  }
  return kilos;
}
