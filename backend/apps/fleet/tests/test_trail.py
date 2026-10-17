"""Stops are found on a route of GPS points (D-167)."""

import datetime as dt

from apps.fleet.trail import distance_m, stops_of

START = dt.datetime(2026, 10, 17, 8, 0, tzinfo=dt.UTC)


def pt(minute, lat=34.74, lng=10.76):
    return {"recorded_at": START + dt.timedelta(minutes=minute), "latitude": lat, "longitude": lng}


def test_distance_is_about_111_metres_per_thousandth_of_a_degree():
    assert round(distance_m(34.74, 10.76, 34.741, 10.76)) == 111


def test_a_truck_that_stays_ten_minutes_made_a_stop():
    route = [pt(0, 34.70), pt(2, 34.72), pt(4), pt(6, 34.74003), pt(8), pt(10, 34.74001), pt(12, 34.76)]

    stops = stops_of(route)

    assert [(s["minutes"], round(s["latitude"], 3)) for s in stops] == [(6, 34.74)]
    assert stops[0]["started_at"] == START + dt.timedelta(minutes=4)
    assert stops[0]["ended_at"] == START + dt.timedelta(minutes=10)


def test_a_short_halt_or_a_moving_truck_is_not_a_stop():
    assert stops_of([pt(0), pt(2), pt(4)]) == []  # four minutes
    assert stops_of([pt(m, 34.74 + m * 0.001) for m in range(0, 20, 2)]) == []  # moving


def test_a_silent_phone_does_not_prove_a_stop():
    assert stops_of([pt(0), pt(30)]) == []  # no point for half an hour at the same place


def test_two_stops_are_found_separately():
    route = [pt(0), pt(6), pt(8, 34.75), pt(10, 34.76), pt(12, 34.76), pt(18, 34.76)]

    assert [s["minutes"] for s in stops_of(route)] == [6, 8]
