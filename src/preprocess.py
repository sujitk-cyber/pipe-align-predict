"""
Preprocessing utilities: clock parsing, feature type normalisation, orientation mapping.
"""

import datetime
import re

import numpy as np


# ---------------------------------------------------------------------------
# Clock position parsing
# ---------------------------------------------------------------------------

def clock_to_degrees(clock_value) -> float | None:
    """Convert a clock-position value to degrees (0-360).

    Convention: 12:00 (top-dead-centre) = 0 deg, increasing clockwise.
      3:00 = 90, 6:00 = 180, 9:00 = 270.

    Accepts strings ("4:30", "12:00", "6"), numeric hours (4.5 -> 135),
    datetime.time objects (from Excel), or NaN/None -> None.
    """
    if clock_value is None or (isinstance(clock_value, float) and np.isnan(clock_value)):
        return None

    if isinstance(clock_value, datetime.time):
        hours = clock_value.hour + clock_value.minute / 60.0
    elif isinstance(clock_value, (int, float)):
        hours = float(clock_value)
    elif isinstance(clock_value, str):
        clock_value = clock_value.strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", clock_value)
        if m:
            hours = int(m.group(1)) + int(m.group(2)) / 60.0
        else:
            try:
                hours = float(clock_value)
            except ValueError:
                return None
    else:
        return None

    hours = hours % 12.0
    return hours * 30.0  # 360 / 12


def clock_distance(deg_a: float | None, deg_b: float | None) -> float | None:
    """Smallest angular difference on a 360-degree circle (range 0-180)."""
    if deg_a is None or deg_b is None:
        return None
    diff = abs(deg_a - deg_b) % 360.0
    return min(diff, 360.0 - diff)


# ---------------------------------------------------------------------------
# Orientation normalisation
# ---------------------------------------------------------------------------

def normalise_orientation(val) -> str | None:
    """Map orientation labels to 'ID' or 'OD'. Returns None if unknown."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    s = str(val).strip().upper()
    if s in ("ID", "INTERNAL", "INT"):
        return "ID"
    if s in ("OD", "EXTERNAL", "EXT"):
        return "OD"
    return s


# ---------------------------------------------------------------------------
# Feature type normalisation
# ---------------------------------------------------------------------------

# Map raw event descriptions to normalised categories.
# Keys are lowercase patterns (checked with str.contains or ==).
FEATURE_TYPE_MAP = {
    "girth weld": "girth_weld",
    "girthweld": "girth_weld",
    "girth weld anomaly": "girth_weld_anomaly",
    "metal loss": "metal_loss",
    "cluster": "metal_loss",        # clusters are groups of metal loss
    "dent": "dent",
    "bend": "bend",
    "field bend": "bend",
    "valve": "valve",
    "tee": "tee",
    "stopple tee": "tee",
    "tap": "tap",
    "flange": "flange",
    "support": "support",
    "attachment": "attachment",
    "agm": "agm",
    "above ground marker": "agm",
    "magnet": "marker",
    "cathodic protection point": "marker",
    # Sleeve / wrap / repair markers
    "sleeve": "sleeve",
    "composite wrap": "composite_wrap",
    "repair marker": "repair_marker",
    "recoat": "recoat",
    "casing": "casing",
    # Manufacturing
    "metal loss manufacturing": "manufacturing_anomaly",
    "metal loss-manufacturing": "manufacturing_anomaly",
    "seam weld manufacturing": "manufacturing_anomaly",
    "seam weld anomaly": "seam_weld_anomaly",
    "seam weld dent": "dent",
    # Area markers (start/end)
    "area start": "area_marker",
    "area end": "area_marker",
    "start ": "area_marker",
    "end ": "area_marker",
}

# Feature types that represent fixed pipeline features (control points)
CONTROL_POINT_TYPES = {"girth_weld", "valve", "tee", "tap", "flange", "bend"}

# Feature types that are compatible for matching across runs
COMPATIBLE_TYPES = {
    "metal_loss": {"metal_loss"},
    "dent": {"dent"},
    "manufacturing_anomaly": {"manufacturing_anomaly"},
    "girth_weld_anomaly": {"girth_weld_anomaly"},
}


def normalise_feature_type(raw: str) -> str:
    """Map a raw event description to a normalised feature type string."""
    if not isinstance(raw, str):
        return "unknown"
    lower = raw.strip().lower()
    # Try exact match first, then substring match (longest match wins)
    for pattern, norm in sorted(FEATURE_TYPE_MAP.items(), key=lambda x: -len(x[0])):
        if lower == pattern or pattern in lower:
            return norm
    return "other"
