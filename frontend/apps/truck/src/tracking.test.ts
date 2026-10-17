import { expect, test } from "vitest";

import { distanceM, type Point, worthKeeping } from "./tracking";

const at = (seconds: number, latitude = 34.74, accuracy: number | null = 10): Point => ({
  client_uuid: String(seconds),
  recorded_at: new Date(Date.UTC(2026, 9, 17, 8, 0, seconds)).toISOString(),
  latitude,
  longitude: 10.76,
  accuracy,
});

test("distance is about 111 m per 0.001 degree of latitude", () => {
  expect(Math.round(distanceM(at(0), at(0, 34.741)))).toBe(111);
});

test("the first precise fix is kept, a vague one is not", () => {
  expect(worthKeeping(null, at(0))).toBe(true);
  expect(worthKeeping(null, at(0, 34.74, 500))).toBe(false);
});

test("too soon or too close is skipped until the heartbeat", () => {
  expect(worthKeeping(at(0), at(10, 34.75))).toBe(false); // moved, but under 30 s
  expect(worthKeeping(at(0), at(60))).toBe(false); // parked
  expect(worthKeeping(at(0), at(60, 34.741))).toBe(true); // moved 111 m
  expect(worthKeeping(at(0), at(125))).toBe(true); // parked, heartbeat
});
