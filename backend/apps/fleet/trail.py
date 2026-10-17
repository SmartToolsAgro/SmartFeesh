"""Stops on a driver's route (D-167): pure functions over the GPS points, no database."""

import datetime as dt
import math
from typing import Any

# The truck stays within this radius of where the stop began.
STOP_RADIUS_M = 50.0
# A stop lasts at least this long, from its first to its last point.
STOP_MIN = dt.timedelta(minutes=5)
# Two points further apart in time than this do not prove the truck stayed (the phone was off or away).
MAX_GAP = dt.timedelta(minutes=15)


def distance_m(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    """Metres between two positions (haversine)."""
    rad = math.pi / 180
    d_lat = (lat_b - lat_a) * rad
    d_lng = (lng_b - lng_a) * rad
    h = math.sin(d_lat / 2) ** 2 + math.cos(lat_a * rad) * math.cos(lat_b * rad) * math.sin(d_lng / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def stops_of(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The places where the truck stayed: `{started_at, ended_at, minutes, latitude, longitude}` in time order.

    `points` are `{recorded_at, latitude, longitude}` in time order. A stop starts at a point and takes the next
    ones while they stay within `STOP_RADIUS_M` of it with no gap above `MAX_GAP`; it counts when it lasts
    `STOP_MIN`. Its position is the average of its points."""
    stops: list[dict[str, Any]] = []
    i = 0
    while i < len(points):
        anchor = points[i]
        j = i
        while j + 1 < len(points):
            nxt = points[j + 1]
            if nxt["recorded_at"] - points[j]["recorded_at"] > MAX_GAP:
                break
            if distance_m(anchor["latitude"], anchor["longitude"], nxt["latitude"], nxt["longitude"]) > STOP_RADIUS_M:
                break
            j += 1
        group = points[i : j + 1]
        started, ended = group[0]["recorded_at"], group[-1]["recorded_at"]
        if ended - started >= STOP_MIN:
            stops.append(
                {
                    "started_at": started,
                    "ended_at": ended,
                    "minutes": int((ended - started).total_seconds() // 60),
                    "latitude": sum(p["latitude"] for p in group) / len(group),
                    "longitude": sum(p["longitude"] for p in group) / len(group),
                }
            )
            i = j + 1
        else:
            i += 1
    return stops
