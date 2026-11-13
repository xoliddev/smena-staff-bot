"""Unit tests for the pure helpers: geofence distance and money/time formatting."""
import pytest

from config import format_currency, format_hours_mins
from utils.geo import calculate_distance, is_within_radius

# A reference point and a point ~111 m north of it (0.001 deg of latitude)
BASE = (41.311081, 69.240562)
NORTH_111M = (41.312081, 69.240562)


def test_distance_to_self_is_zero():
    assert calculate_distance(*BASE, *BASE) == 0


def test_distance_one_millidegree_latitude():
    assert calculate_distance(*BASE, *NORTH_111M) == pytest.approx(111.2, abs=0.5)


def test_distance_is_symmetric():
    assert calculate_distance(*BASE, *NORTH_111M) == calculate_distance(*NORTH_111M, *BASE)


@pytest.mark.parametrize("radius, inside", [(150, True), (100, False)])
def test_is_within_radius(radius, inside):
    ok, dist = is_within_radius(*NORTH_111M, *BASE, radius)
    assert ok is inside
    assert dist == pytest.approx(111.2, abs=0.5)


@pytest.mark.parametrize("amount, expected", [
    (None, "0 so'm"),
    (0, "0 so'm"),
    (1500000, "1 500 000 so'm"),
    (2500.5, "2 500.50 so'm"),
])
def test_format_currency(amount, expected):
    assert format_currency(amount) == expected


@pytest.mark.parametrize("hours, expected", [
    (None, "0 soat"),
    (8, "8 soat"),
    (8.5, "8 soat 30 daq"),
    (0.25, "15 daqiqa"),
])
def test_format_hours_mins(hours, expected):
    assert format_hours_mins(hours) == expected
