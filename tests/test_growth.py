"""Tests for src/growth.py — growth rates, severity, forecasting, non-linear models."""

import numpy as np
import pandas as pd
import pytest

from src.growth import (
    compute_growth_rates,
    estimate_remaining_life,
    compute_severity_score,
    growth_summary_stats,
    forecast_depth,
    fit_single_model,
    select_best_model,
    forecast_nonlinear,
    multi_run_growth_analysis,
    compute_aic,
    compute_bic,
    detect_acceleration,
    add_years_to_80pct,
    run_growth_analysis,
)


class TestComputeGrowthRates:
    def test_basic(self, matched_df):
        result = compute_growth_rates(matched_df, years_between=7.0)
        assert "depth_growth_pct_per_yr" in result.columns
        assert "negative_growth_flag" in result.columns
        # depth_B > depth_A for all, so no negative flags
        assert result["negative_growth_flag"].sum() == 0

    def test_negative_growth_flagged(self):
        df = pd.DataFrame({
            "depth_pct_a": [30.0], "depth_pct_b": [25.0],
            "length_a": [2.0], "length_b": [2.0],
            "width_a": [1.0], "width_b": [1.0],
        })
        result = compute_growth_rates(df, 5.0)
        assert result["negative_growth_flag"].iloc[0] == True

    def test_empty_df(self):
        result = compute_growth_rates(pd.DataFrame(), 5.0)
        assert result.empty

    def test_invalid_years(self, matched_df):
        with pytest.raises(ValueError):
            compute_growth_rates(matched_df, 0)


class TestEstimateRemainingLife:
    def test_positive_growth(self):
        df = pd.DataFrame({
            "depth_pct_b": [40.0],
            "depth_growth_pct_per_yr": [5.0],
        })
        result = estimate_remaining_life(df, critical_depth_pct=80.0)
        assert result["remaining_life_yr"].iloc[0] == pytest.approx(8.0)

    def test_already_critical(self):
        df = pd.DataFrame({
            "depth_pct_b": [85.0],
            "depth_growth_pct_per_yr": [5.0],
        })
        result = estimate_remaining_life(df, critical_depth_pct=80.0)
        assert result["remaining_life_yr"].iloc[0] == 0.0
        assert result["already_critical_flag"].iloc[0] == True

    def test_negative_growth_infinite_life(self):
        df = pd.DataFrame({
            "depth_pct_b": [40.0],
            "depth_growth_pct_per_yr": [-1.0],
        })
        result = estimate_remaining_life(df)
        assert result["remaining_life_yr"].iloc[0] == np.inf


class TestSeverityScore:
    def test_range(self, matched_df):
        df = compute_growth_rates(matched_df, 7.0)
        df = estimate_remaining_life(df)
        df = compute_severity_score(df)
        assert all(0 <= s <= 100 for s in df["severity_score"])

    def test_sorted_descending(self, matched_df):
        df = compute_growth_rates(matched_df, 7.0)
        df = estimate_remaining_life(df)
        df = compute_severity_score(df)
        scores = df["severity_score"].tolist()
        assert scores == sorted(scores, reverse=True)


class TestGrowthSummaryStats:
    def test_basic(self, matched_df):
        df = compute_growth_rates(matched_df, 7.0)
        summary = growth_summary_stats(df)
        assert "feature_type" in summary.columns
        assert "mean_growth" in summary.columns

    def test_empty(self):
        assert growth_summary_stats(pd.DataFrame()).empty


class TestForecastDepth:
    def test_projects_forward(self):
        df = pd.DataFrame({
            "depth_pct_b": [40.0],
            "depth_growth_pct_per_yr": [2.0],
        })
        result = forecast_depth(df, forecast_years=5)
        assert result["projected_depth_pct"].iloc[0] == pytest.approx(50.0)


class TestNonLinearModels:
    def test_fit_linear(self):
        t = np.array([0, 5, 10, 15], dtype=float)
        d = 10.0 + 2.0 * t  # perfect linear
        result = fit_single_model(t, d, "linear")
        assert result is not None
        assert result["model_name"] == "linear"
        assert result["rss"] < 0.01

    def test_select_best(self):
        t = np.array([0, 5, 10, 15], dtype=float)
        d = 10.0 + 2.0 * t
        best = select_best_model(t, d)
        assert best is not None
        assert "all_fits" in best

    def test_forecast_nonlinear(self):
        t = np.array([0, 5, 10], dtype=float)
        d = 10.0 + 2.0 * t
        best = select_best_model(t, d)
        projected = forecast_nonlinear(best, 5.0, 10.0)
        assert projected is not None
        assert projected == pytest.approx(40.0, rel=0.1)

    def test_insufficient_data(self):
        result = fit_single_model(np.array([0.0]), np.array([10.0]), "linear")
        assert result is None


class TestMultiRunGrowthAnalysis:
    def test_three_runs(self):
        result = multi_run_growth_analysis(
            "anom_1", times=[0, 8, 15], depths=[10.0, 18.0, 26.0],
        )
        assert result["n_runs"] == 3
        assert result["best_model"] is not None

    def test_two_runs_fallback(self):
        result = multi_run_growth_analysis("anom_2", times=[0, 8], depths=[10.0, 18.0])
        assert result["best_model"] == "linear_2pt"
        assert result["growth_rate_pct_per_yr"] == pytest.approx(1.0)


class TestAIC_BIC:
    def test_aic(self):
        assert compute_aic(10, 2, 1.0) < compute_aic(10, 5, 1.0)

    def test_bic(self):
        assert compute_bic(10, 2, 1.0) < compute_bic(10, 5, 1.0)

    def test_edge_cases(self):
        assert compute_aic(0, 2, 1.0) == np.inf
        assert compute_bic(10, 2, 0.0) == np.inf


class TestDetectAcceleration:
    def test_accelerating(self):
        result = detect_acceleration([1.0, 2.0], [8, 7])
        assert result["acceleration_flag"] is True

    def test_stable(self):
        result = detect_acceleration([1.0, 1.1], [8, 7])
        assert result["acceleration_flag"] is False

    def test_decelerating(self):
        result = detect_acceleration([2.0, 0.5], [8, 7])
        assert result["acceleration_flag"] is False
        assert "decelerating" in result["description"]

    def test_insufficient_data(self):
        result = detect_acceleration([1.0], [8])
        assert result["acceleration_flag"] is False


class TestAddYearsTo80Pct:
    def test_basic(self):
        df = pd.DataFrame({
            "depth_pct_b": [40.0],
            "depth_growth_pct_per_yr": [4.0],
        })
        result = add_years_to_80pct(df)
        assert result["years_to_80pct"].iloc[0] == pytest.approx(10.0)


class TestRunGrowthAnalysis:
    def test_full_pipeline(self, matched_df):
        growth_df, summary_df = run_growth_analysis(matched_df, years_between=7.0)
        assert "severity_score" in growth_df.columns
        assert "years_to_80pct" in growth_df.columns
        assert not summary_df.empty
