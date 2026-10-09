import { useEffect, useState } from "react";

type Status = "checking" | "ok" | "down";

/** Shows whether the backend answers. Temporary scaffold check; replaced by real screens later. */
export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/v1/health", { signal: controller.signal })
      .then((response) => setStatus(response.ok ? "ok" : "down"))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setStatus("down");
      });
    return () => controller.abort();
  }, []);

  const label = { checking: "Connexion au serveur…", ok: "Serveur connecté", down: "Serveur injoignable" }[status];
  return (
    <p role="status" data-status={status}>
      {label}
    </p>
  );
}
