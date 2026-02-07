"""Tests for src/preprocess.py — clock parsing, feature type normalisation, orientation."""

import datetime
import math

import numpy as np
import pytest

from src.preprocess import (
    clock_to_degrees,
    clock_distance,
    normalise_orientation,
    normalise_feature_type,
    CONTROL_POINT_TYPES,
    COMPATIBLE_TYPES,
)


# ---------------------------------------------------------------------------
# clock_to_degrees
# ---------------------------------------------------------------------------

class TestClockToDegrees:
    @pytest.mark.parametrize("inp, expected", [
        ("12:00", 0.0),
        ("3:00", 90.0),
        ("6:00", 180.0),
        ("9:00", 270.0),
        ("1:30", 45.0),
        ("4:30", 135.0),
        (3.0, 90.0),
        (6, 180.0),
        (12, 0.0),       # 12 % 12 = 0
        (0, 0.0),        # 0 % 12 = 0
        (4.5, 135.0),
    ])
    def test_valid_values(self, inp, expected):
        assert clock_to_degrees(inp) == pytest.approx(expected, abs=0.1)

    def test_datetime_time(self):
        assert clock_to_degrees(datetime.time(3, 0)) == pytest.approx(90.0)
        assert clock_to_degrees(datetime.time(6, 30)) == pytest.approx(195.0)

    @pytest.mark.parametrize("inp", [None, float("nan"), "abc", ""])
    def test_returns_none(self, inp):
        assert clock_to_degrees(inp) is None


# ---------------------------------------------------------------------------
# clock_distance
# ---------------------------------------------------------------------------

class TestClockDistance:
    @pytest.mark.parametrize("a, b, expected", [
        (0.0, 90.0, 90.0),
        (350.0, 10.0, 20.0),   # wraparound
        (0.0, 180.0, 180.0),
        (90.0, 90.0, 0.0),
        (270.0, 90.0, 180.0),
    ])
    def test_values(self, a, b, expected):
        assert clock_distance(a, b) == pytest.approx(expected)

    def test_none_inputs(self):
        assert clock_distance(None, 90.0) is None
        assert clock_distance(90.0, None) is None
        assert clock_distance(None, None) is None


# ---------------------------------------------------------------------------
# normalise_orientation
# ---------------------------------------------------------------------------

class TestNormaliseOrientation:
    @pytest.mark.parametrize("inp, expected", [
        ("ID", "ID"), ("id", "ID"), ("Internal", "ID"), ("INT", "ID"),
        ("OD", "OD"), ("od", "OD"), ("External", "OD"), ("EXT", "OD"),
    ])
    def test_known(self, inp, expected):
        assert normalise_orientation(inp) == expected

    def test_none_and_nan(self):
        assert normalise_orientation(None) is None
        assert normalise_orientation(float("nan")) is None

    def test_unknown_passthrough(self):
        assert normalise_orientation("BOTH") == "BOTH"


# ---------------------------------------------------------------------------
# normalise_feature_type
# ---------------------------------------------------------------------------

class TestNormaliseFeatureType:
    @pytest.mark.parametrize("inp, expected", [
        ("Girth Weld", "girth_weld"),
        ("GIRTH WELD", "girth_weld"),
        ("Metal Loss", "metal_loss"),
        ("Dent", "dent"),
        ("Valve", "valve"),
        ("Tee", "tee"),
        ("Field Bend", "bend"),
        ("Area Start Launcher", "area_marker"),
    ])
    def test_known(self, inp, expected):
        assert normalise_feature_type(inp) == expected

    def test_unknown(self):
        assert normalise_feature_type("some random text") == "other"

    def test_non_string(self):
        assert normalise_feature_type(None) == "unknown"
        assert normalise_feature_type(123) == "unknown"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_control_point_types_are_set():
    assert isinstance(CONTROL_POINT_TYPES, set)
    assert "girth_weld" in CONTROL_POINT_TYPES

def test_compatible_types_keys():
    for k, v in COMPATIBLE_TYPES.items():
        assert isinstance(v, set)
