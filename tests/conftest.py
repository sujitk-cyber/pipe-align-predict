"""Shared fixtures for the ILI pipeline test suite."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def canonical_df_a():
    """Small canonical Run A DataFrame for testing."""
    return pd.DataFrame({
        "run_id": "run_a",
        "feature_id": [f"a_{i}" for i in range(10)],
        "distance": [0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0],
        "joint_number": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "relative_position": np.nan,
        "clock_position_raw": ["12:00", "3:00", "6:00", "9:00", "12:00",
                                "3:00", "6:00", "9:00", "12:00", "3:00"],
        "clock_deg": [0.0, 90.0, 180.0, 270.0, 0.0, 90.0, 180.0, 270.0, 0.0, 90.0],
        "feature_type_raw": [
            "Girth Weld", "Metal Loss", "Metal Loss", "Girth Weld", "Dent",
            "Metal Loss", "Girth Weld", "Metal Loss", "Metal Loss", "Girth Weld",
        ],
        "feature_type_norm": [
            "girth_weld", "metal_loss", "metal_loss", "girth_weld", "dent",
            "metal_loss", "girth_weld", "metal_loss", "metal_loss", "girth_weld",
        ],
        "orientation": [None, "OD", "OD", None, "OD", "ID", None, "OD", "OD", None],
        "depth_percent": [np.nan, 15.0, 25.0, np.nan, 5.0, 30.0, np.nan, 10.0, 40.0, np.nan],
        "length": [np.nan, 2.0, 3.0, np.nan, 1.5, 4.0, np.nan, 2.5, 5.0, np.nan],
        "width": [np.nan, 1.0, 1.5, np.nan, 0.5, 2.0, np.nan, 1.0, 2.5, np.nan],
        "wall_thickness": [0.344] * 10,
    })


@pytest.fixture
def canonical_df_b():
    """Small canonical Run B DataFrame (slight distance offset from Run A)."""
    return pd.DataFrame({
        "run_id": "run_b",
        "feature_id": [f"b_{i}" for i in range(10)],
        "distance": [2.0, 103.0, 202.0, 302.0, 403.0, 503.0, 603.0, 703.0, 803.0, 903.0],
        "joint_number": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "relative_position": np.nan,
        "clock_position_raw": ["12:00", "3:00", "6:00", "9:00", "12:00",
                                "3:00", "6:00", "9:00", "12:00", "3:00"],
        "clock_deg": [0.0, 90.0, 180.0, 270.0, 0.0, 90.0, 180.0, 270.0, 0.0, 90.0],
        "feature_type_raw": [
            "Girth Weld", "Metal Loss", "Metal Loss", "Girth Weld", "Dent",
            "Metal Loss", "Girth Weld", "Metal Loss", "Metal Loss", "Girth Weld",
        ],
        "feature_type_norm": [
            "girth_weld", "metal_loss", "metal_loss", "girth_weld", "dent",
            "metal_loss", "girth_weld", "metal_loss", "metal_loss", "girth_weld",
        ],
        "orientation": [None, "OD", "OD", None, "OD", "ID", None, "OD", "OD", None],
        "depth_percent": [np.nan, 18.0, 30.0, np.nan, 6.0, 35.0, np.nan, 12.0, 45.0, np.nan],
        "length": [np.nan, 2.2, 3.5, np.nan, 1.7, 4.5, np.nan, 2.8, 5.5, np.nan],
        "width": [np.nan, 1.1, 1.7, np.nan, 0.6, 2.2, np.nan, 1.1, 2.8, np.nan],
        "wall_thickness": [0.344] * 10,
    })


@pytest.fixture
def matched_df():
    """Pre-built matched anomaly DataFrame for growth/reporting tests."""
    return pd.DataFrame({
        "feature_id_a": ["a_1", "a_2", "a_4", "a_5", "a_7", "a_8"],
        "feature_id_b": ["b_1", "b_2", "b_4", "b_5", "b_7", "b_8"],
        "distance_a": [100.0, 200.0, 400.0, 500.0, 700.0, 800.0],
        "corrected_distance_b": [100.5, 200.3, 400.1, 500.2, 700.4, 800.1],
        "distance_b_raw": [103.0, 202.0, 403.0, 503.0, 703.0, 803.0],
        "delta_dist_ft": [0.5, 0.3, 0.1, 0.2, 0.4, 0.1],
        "clock_deg_a": [90.0, 180.0, 0.0, 90.0, 270.0, 0.0],
        "clock_deg_b": [90.0, 180.0, 0.0, 90.0, 270.0, 0.0],
        "delta_clock_deg": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "feature_type": ["metal_loss"] * 6,
        "orientation": ["OD", "OD", "OD", "ID", "OD", "OD"],
        "depth_pct_a": [15.0, 25.0, 5.0, 30.0, 10.0, 40.0],
        "depth_pct_b": [18.0, 30.0, 6.0, 35.0, 12.0, 45.0],
        "length_a": [2.0, 3.0, 1.5, 4.0, 2.5, 5.0],
        "length_b": [2.2, 3.5, 1.7, 4.5, 2.8, 5.5],
        "width_a": [1.0, 1.5, 0.5, 2.0, 1.0, 2.5],
        "width_b": [1.1, 1.7, 0.6, 2.2, 1.1, 2.8],
        "wall_thickness_a": [0.344] * 6,
        "wall_thickness_b": [0.344] * 6,
        "cost": [1.5, 2.0, 0.8, 1.2, 1.0, 0.5],
        "segment_id": [0, 0, 1, 1, 2, 2],
        "status": ["MATCHED", "MATCHED", "MATCHED", "MATCHED", "MATCHED", "UNCERTAIN"],
    })


@pytest.fixture
def sample_csv(tmp_path):
    """Create a small sample CSV file and return its path."""
    df = pd.DataFrame({
        "J. no.": [1, 2, 3, 4, 5],
        "Log Dist. [ft]": [100.0, 200.0, 300.0, 400.0, 500.0],
        "Event Description": ["Girth Weld", "Metal Loss", "Dent", "Girth Weld", "Metal Loss"],
        "Depth [%]": [np.nan, 20.0, 5.0, np.nan, 30.0],
        "O'clock": ["12:00", "3:00", "6:00", "9:00", "12:00"],
        "ID/OD": [None, "OD", "OD", None, "ID"],
        "Length [in]": [np.nan, 2.0, 1.0, np.nan, 3.0],
        "Width [in]": [np.nan, 1.0, 0.5, np.nan, 1.5],
        "Wt [in]": [0.344] * 5,
    })
    path = tmp_path / "sample.csv"
    df.to_csv(path, index=False)
    return path
