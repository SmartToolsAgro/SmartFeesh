import { useEffect, useState } from "react";

import { forgetPriceWatch } from "./priceWatch";
import { forgetPurchaseWatch } from "./purchaseWatch";
import { forgetRecentCustomers } from "./recentCustomers";

/** True while the phone has a connection. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

/** Lets the app open without signal once it has been opened once (public/sw.js, D-096). */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });
}

/** Forget what the phone saved of the API, so the next person on this phone sees nothing of the last one. */
export async function forgetSavedData(): Promise<void> {
  forgetPriceWatch();
  forgetPurchaseWatch();
  forgetRecentCustomers();
  if (!("caches" in window)) return;
  const names = await caches.keys();
  await Promise.all(names.filter((name) => name.startsWith("frutti-truck-data")).map((name) => caches.delete(name)));
}
