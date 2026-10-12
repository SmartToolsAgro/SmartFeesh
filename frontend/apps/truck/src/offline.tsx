import { useTranslation } from "@frutti/i18n";
import { useEffect, useState } from "react";

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

/** One calm line at the top of the screens while there is no signal. */
export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useOnline();
  if (online) return null;
  return (
    <p role="status" className="mb-4 rounded-control bg-warn-soft px-3 py-2 text-warn">
      {t("truck.offline.banner")}
    </p>
  );
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
  if (!("caches" in window)) return;
  const names = await caches.keys();
  await Promise.all(names.filter((name) => name.startsWith("frutti-truck-data")).map((name) => caches.delete(name)));
}
