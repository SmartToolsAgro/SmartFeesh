import { type RoutePoint, useGetDayRoute } from "@frutti/api";
import { formatDateTime, useTranslation } from "@frutti/i18n";
import { Card } from "@frutti/ui";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

/** A driver whose last point is older than this is "not seen" while his day runs. */
const SILENT_AFTER_MS = 10 * 60_000;
const REFRESH_MS = 30_000;
const LINE = "#1f6f8b";

/** The route of a driver's day on OpenStreetMap: the line, the start, and the truck where it was last seen (D-166). */
function RouteCanvas({ points }: { points: readonly RoutePoint[] }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fitted = useRef(false);

  useEffect(() => {
    if (container.current === null) return;
    const created = L.map(container.current, { scrollWheelZoom: false }).setView([34.74, 10.76], 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap",
    }).addTo(created);
    map.current = created;
    layer.current = L.layerGroup().addTo(created);
    // The dialog is still opening: measure the box again once it has its size.
    const timer = window.setTimeout(() => created.invalidateSize(), 250);
    return () => {
      window.clearTimeout(timer);
      created.remove();
      map.current = null;
      layer.current = null;
      fitted.current = false;
    };
  }, []);

  useEffect(() => {
    const group = layer.current;
    const current = map.current;
    if (group === null || current === null) return;
    group.clearLayers();
    if (points.length === 0) return;
    const path: L.LatLngTuple[] = points.map((p) => [p.latitude, p.longitude]);
    L.polyline(path, { color: LINE, weight: 4, opacity: 0.8 }).addTo(group);
    L.circleMarker(path[0]!, { radius: 7, color: "#fff", weight: 2, fillColor: "#2e9e5b", fillOpacity: 1 }).addTo(
      group,
    );
    L.circleMarker(path[path.length - 1]!, {
      radius: 10,
      color: "#fff",
      weight: 3,
      fillColor: "#d64545",
      fillOpacity: 1,
    }).addTo(group);
    if (!fitted.current) {
      current.fitBounds(L.latLngBounds(path), { padding: [30, 30], maxZoom: 17 });
      fitted.current = true;
    }
  }, [points]);

  return <div ref={container} className="h-72 w-full overflow-hidden rounded-control" />;
}

export function RouteMap({ dayId, running }: { dayId: number; running: boolean }) {
  const { t } = useTranslation();
  const k = "admin.dayOverview.detail.route";
  const route = useGetDayRoute(dayId, { query: { refetchInterval: running ? REFRESH_MS : false } });
  const points = route.data?.points ?? [];
  const last = route.data?.last ?? null;
  const silent = running && last !== null && route.dataUpdatedAt - Date.parse(last.recorded_at) > SILENT_AFTER_MS;
  return (
    <Card className="space-y-2 p-4">
      {route.isError ? (
        <p className="text-ink-2">{t("common.serverUnreachable")}</p>
      ) : last === null ? (
        <p className="text-ink-2">{route.isPending ? t("common.loading") : t(`${k}.empty`)}</p>
      ) : (
        <>
          <p className={silent ? "text-warn" : "text-ink-2"}>
            {t(`${k}.lastSeen`, { when: formatDateTime(last.recorded_at) })}
            {silent && ` · ${t(`${k}.silent`)}`}
          </p>
          <RouteCanvas points={points} />
          <p className="text-[0.8rem] text-ink-2">{t(`${k}.legend`, { count: points.length })}</p>
        </>
      )}
    </Card>
  );
}
