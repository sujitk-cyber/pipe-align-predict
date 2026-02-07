"""Tests for src/matching.py — cost function, Hungarian matching, segment assignment."""

import numpy as np
import pandas as pd
import pytest

from src.matching import (
    types_compatible,
    compute_pair_cost,
    match_anomalies,
    DEFAULT_WEIGHTS,
)


class TestTypesCompatible:
    def test_same_type(self):
        assert types_compatible("metal_loss", "metal_loss") is True

    def test_different_incompatible(self):
        assert types_compatible("metal_loss", "dent") is False

    def test_compatible_via_map(self):
        # metal_loss maps to {metal_loss}
        assert types_compatible("metal_loss", "metal_loss") is True


class TestComputePairCost:
    def _make_row(self, **kwargs):
        defaults = {
            "distance": 100.0,
            "corrected_distance": 100.0,
            "clock_deg": 90.0,
            "depth_percent": 20.0,
            "length": 2.0,
            "width": 1.0,
            "feature_type_norm": "metal_loss",
            "orientation": "OD",
        }
        defaults.update(kwargs)
        return pd.Series(defaults)

    def test_identical_pair_zero_cost(self):
        row = self._make_row()
        cost = compute_pair_cost(row, row)
        assert cost == pytest.approx(0.0)

    def test_orientation_mismatch_returns_none(self):
        a = self._make_row(orientation="ID")
        b = self._make_row(orientation="OD")
        assert compute_pair_cost(a, b) is None

    def test_incompatible_type_returns_none(self):
        a = self._make_row(feature_type_norm="metal_loss")
        b = self._make_row(feature_type_norm="dent")
        assert compute_pair_cost(a, b) is None

    def test_cost_increases_with_distance(self):
        a = self._make_row(distance=100.0)
        b_near = self._make_row(corrected_distance=101.0)
        b_far = self._make_row(corrected_distance=110.0)
        c_near = compute_pair_cost(a, b_near)
        c_far = compute_pair_cost(a, b_far)
        assert c_far > c_near


class TestMatchAnomalies:
    def test_basic_matching(self, canonical_df_a, canonical_df_b):
        from src.alignment import align_runs
        df_b_aligned, segments, matched_cp, residuals = align_runs(
            canonical_df_a, canonical_df_b
        )
        matched_df, missing_df, new_df = match_anomalies(
            canonical_df_a, df_b_aligned, matched_cp,
        )
        # Should produce at least some matches
        assert len(matched_df) + len(missing_df) + len(new_df) > 0

    def test_status_column(self, canonical_df_a, canonical_df_b):
        from src.alignment import align_runs
        df_b_aligned, segments, matched_cp, _ = align_runs(
            canonical_df_a, canonical_df_b
        )
        matched_df, missing_df, new_df = match_anomalies(
            canonical_df_a, df_b_aligned, matched_cp,
        )
        if not matched_df.empty:
            assert "status" in matched_df.columns
            assert all(s in ("MATCHED", "UNCERTAIN") for s in matched_df["status"])
        if not missing_df.empty:
            assert all(missing_df["status"] == "MISSING")
        if not new_df.empty:
            assert all(new_df["status"] == "NEW")

    def test_empty_runs(self):
        empty = pd.DataFrame(columns=[
            "feature_id", "distance", "clock_deg", "feature_type_norm",
            "orientation", "depth_percent", "length", "width",
        ])
        cp = pd.DataFrame(columns=["distance_a"])
        matched, missing, new = match_anomalies(empty, empty, cp)
        assert matched.empty
