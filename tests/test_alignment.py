"""Tests for src/alignment.py — control points, matching, piecewise alignment."""

import numpy as np
import pandas as pd
import pytest

from src.alignment import (
    extract_control_points,
    match_control_points_by_joint,
    match_control_points_by_sequence,
    match_control_points,
    compute_piecewise_transforms,
    apply_alignment,
    compute_residuals,
    align_runs,
)


class TestExtractControlPoints:
    def test_filters_control_types(self, canonical_df_a):
        cp = extract_control_points(canonical_df_a)
        assert all(t in {"girth_weld", "valve", "tee", "tap", "flange", "bend"}
                   for t in cp["feature_type_norm"])

    def test_sorted_by_distance(self, canonical_df_a):
        cp = extract_control_points(canonical_df_a)
        assert list(cp["distance"]) == sorted(cp["distance"])


class TestMatchControlPointsByJoint:
    def test_matches_by_joint_number(self, canonical_df_a, canonical_df_b):
        cp_a = extract_control_points(canonical_df_a)
        cp_b = extract_control_points(canonical_df_b)
        matched = match_control_points_by_joint(cp_a, cp_b)
        assert len(matched) > 0
        assert "distance_a" in matched.columns
        assert "distance_b" in matched.columns

    def test_empty_when_no_joint_numbers(self):
        cp_a = pd.DataFrame({
            "joint_number": [np.nan],
            "distance": [100.0],
            "feature_type_norm": ["girth_weld"],
        })
        cp_b = cp_a.copy()
        matched = match_control_points_by_joint(cp_a, cp_b)
        assert matched.empty


class TestMatchControlPointsBySequence:
    def test_sequence_matching(self, canonical_df_a, canonical_df_b):
        cp_a = extract_control_points(canonical_df_a)
        cp_b = extract_control_points(canonical_df_b)
        matched = match_control_points_by_sequence(cp_a, cp_b)
        assert len(matched) > 0


class TestComputePiecewiseTransforms:
    def test_basic_segments(self):
        cp = pd.DataFrame({
            "distance_a": [0.0, 100.0, 200.0],
            "distance_b": [2.0, 103.0, 202.0],
        })
        segments = compute_piecewise_transforms(cp)
        assert len(segments) == 2
        for seg in segments:
            assert "scale" in seg
            assert "shift" in seg

    def test_single_point_fallback(self):
        cp = pd.DataFrame({"distance_a": [100.0], "distance_b": [102.0]})
        segments = compute_piecewise_transforms(cp)
        assert len(segments) == 1
        assert segments[0]["scale"] == 1.0
        assert segments[0]["shift"] == pytest.approx(-2.0)

    def test_no_points_fallback(self):
        cp = pd.DataFrame({"distance_a": [], "distance_b": []})
        segments = compute_piecewise_transforms(cp)
        assert len(segments) == 1
        assert segments[0]["shift"] == 0.0


class TestApplyAlignment:
    def test_corrects_distances(self, canonical_df_b):
        segments = [{"seg_id": 0, "b_start": -np.inf, "b_end": np.inf,
                      "a_start": -np.inf, "a_end": np.inf,
                      "scale": 1.0, "shift": -3.0}]
        cp = pd.DataFrame({"distance_a": [0.0], "distance_b": [3.0]})
        result = apply_alignment(canonical_df_b, segments, cp)
        assert "corrected_distance" in result.columns
        # With shift=-3, corrected = distance - 3
        assert result["corrected_distance"].iloc[0] == pytest.approx(-1.0)


class TestComputeResiduals:
    def test_residuals_near_zero(self):
        cp = pd.DataFrame({"distance_a": [100.0, 200.0], "distance_b": [102.0, 203.0]})
        segments = compute_piecewise_transforms(cp)
        residuals = compute_residuals(cp, segments)
        # At control points, residuals should be very close to zero
        assert all(abs(r) < 0.01 for r in residuals["residual_ft"])


class TestAlignRuns:
    def test_full_pipeline(self, canonical_df_a, canonical_df_b):
        df_b_aligned, segments, matched_cp, residuals = align_runs(
            canonical_df_a, canonical_df_b
        )
        assert "corrected_distance" in df_b_aligned.columns
        assert len(segments) > 0
        assert not matched_cp.empty
