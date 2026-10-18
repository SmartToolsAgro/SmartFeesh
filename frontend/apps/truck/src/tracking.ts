import { recordMyLocations } from "@frutti/api";
import { useEffect, useState } from "react";

import { newUuid } from "./uuid";

// The phone follows the day while it runs (D-164): a GPS point every so often, kept on the phone until the server
// has taken it. A web page only gets the position while it is open, so gaps are normal when the screen is off.

export interface Point {
  client_uuid: string;
  recorded_at: string;
  latitude: number;
  longitude: number;
  accuracy: number | null;
}

/** A point only counts if it is precise enough to place the truck. */
export const MAX_ACCURACY_M = 100;
/** Two kept points are at least this far apart in time. */
export const MIN_GAP_MS = 30_000;
/** Moved less than this since the last kept point: wait for a heartbeat instead. */
export const MIN_MOVE_M = 15;
/** A parked truck still sends one point this often, so a stop shows how long it lasted. */
export const HEARTBEAT_MS = 120_000;
export const SEND_EVERY_MS = 60_000;
export const BATCH = 200;
/** What the phone keeps without signal: about a day of heartbeats and trips. */
export const MAX_WAITING = 3000;

const KEY = "frutti-truck-pings";

/** Metres between two positions (haversine). */
export function distanceM(
  a: { latitude: number; longitude: number },
  b: { latitude: number; longitude: number },
): number {
  const rad = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * rad;
  const dLng = (b.longitude - a.longitude) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}

/** Whether a new fix is worth keeping after the last kept point. */
export function worthKeeping(last: Point | null, next: Point): boolean {
  if (next.accuracy !== null && next.accuracy > MAX_ACCURACY_M) return false;
  if (last === null) return true;
  const elapsed = Date.parse(next.recorded_at) - Date.parse(last.recorded_at);
  if (elapsed < MIN_GAP_MS) return false;
  return elapsed >= HEARTBEAT_MS || distanceM(last, next) >= MIN_MOVE_M;
}

export function waitingPoints(): Point[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(parsed) ? (parsed as Point[]) : [];
  } catch {
    return [];
  }
}

function saveWaiting(points: Point[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(points.slice(-MAX_WAITING)));
  } catch {
    // Storage blocked or full: the points not sent yet are lost, the day goes on.
  }
}

export function keepPoint(point: Point): void {
  saveWaiting([...waitingPoints(), point]);
}

/** Forget the points of the last person on this phone. */
export function forgetPoints(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to forget.
  }
}

/** Send what is waiting, 200 at a time; what the server took leaves the phone. A failure keeps everything. */
export async function sendWaitingPoints(): Promise<void> {
  for (;;) {
    const batch = waitingPoints().slice(0, BATCH);
    if (batch.length === 0) return;
    try {
      await recordMyLocations({
        points: batch.map((point) => ({
          client_uuid: point.client_uuid,
          recorded_at: point.recorded_at,
          latitude: point.latitude.toFixed(6),
          longitude: point.longitude.toFixed(6),
          accuracy: point.accuracy === null ? null : point.accuracy.toFixed(1),
        })),
      });
    } catch {
      return;
    }
    const sent = new Set(batch.map((point) => point.client_uuid));
    saveWaiting(waitingPoints().filter((point) => !sent.has(point.client_uuid)));
  }
}

/** GPS tracking is switched off with the route map (D-180); set to true to follow the day again. */
export const TRACKING_ENABLED = false;

export type TrackingState = "off" | "active" | "denied" | "unavailable";

/** Follow the position while `enabled` (the day runs on the phone): keep the useful fixes and send them. */
export function useLocationTracking(enabled: boolean): TrackingState {
  const [state, setState] = useState<TrackingState>("off");
  useEffect(() => {
    if (!enabled || !("geolocation" in navigator)) return;
    let last: Point | null = waitingPoints().at(-1) ?? null;
    const watch = navigator.geolocation.watchPosition(
      (position) => {
        setState("active");
        const point: Point = {
          client_uuid: newUuid(),
          recorded_at: new Date(position.timestamp).toISOString(),
          latitude: Number(position.coords.latitude.toFixed(6)),
          longitude: Number(position.coords.longitude.toFixed(6)),
          accuracy: Number.isFinite(position.coords.accuracy) ? Math.round(position.coords.accuracy * 10) / 10 : null,
        };
        if (!worthKeeping(last, point)) return;
        last = point;
        keepPoint(point);
      },
      (error) => setState(error.code === error.PERMISSION_DENIED ? "denied" : "unavailable"),
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 60_000 },
    );
    const send = () => void sendWaitingPoints();
    const timer = window.setInterval(send, SEND_EVERY_MS);
    const hidden = () => {
      if (document.visibilityState === "hidden") send();
    };
    window.addEventListener("online", send);
    document.addEventListener("visibilitychange", hidden);
    send();
    return () => {
      navigator.geolocation.clearWatch(watch);
      window.clearInterval(timer);
      window.removeEventListener("online", send);
      document.removeEventListener("visibilitychange", hidden);
    };
  }, [enabled]);
  if (!enabled) return "off";
  return "geolocation" in navigator ? state : "unavailable";
}
