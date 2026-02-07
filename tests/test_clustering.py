"""Tests for src/clustering.py — DBSCAN anomaly clustering."""

import numpy as np
import pandas as pd
import pytest

from src.clustering import (
    cluster_anomalies,
    compute_cluster_metrics,
    write_clusters_summary,
)


@pytest.fixture
def clusterable_df():
    """DataFrame with two clear spatial clusters."""
    return pd.DataFrame({
        "feature_id_a": [f"a_{i}" for i in range(8)],
        "distance_a": [100, 110, 120, 130, 500, 510, 520, 530],
        "clock_deg_a": [90, 95, 85, 90, 270, 275, 265, 270],
        "depth_pct_b": [20, 25, 30, 15, 40, 45, 35, 50],
        "depth_growth_pct_per_yr": [1.0, 1.5, 2.0, 0.5, 3.0, 3.5, 2.5, 4.0],
        "length_b": [2.0, 2.5, 3.0, 1.5, 4.0, 4.5, 3.5, 5.0],
        "width_b": [1.0, 1.2, 1.5, 0.8, 2.0, 2.2, 1.8, 2.5],
    })


class TestClusterAnomalies:
    def test_1d_clustering(self, clusterable_df):
        result = cluster_anomalies(clusterable_df, epsilon=50, mode="1d")
        assert "cluster_id" in result.columns
        # Two groups well separated by ~370 ft → should get 2 clusters
        n_clusters = result["cluster_id"][result["cluster_id"] >= 0].nunique()
        assert n_clusters == 2

    def test_2d_clustering(self, clusterable_df):
        result = cluster_anomalies(clusterable_df, epsilon=50, mode="2d")
        assert "cluster_id" in result.columns

    def test_large_epsilon_single_cluster(self, clusterable_df):
        result = cluster_anomalies(clusterable_df, epsilon=1000, mode="1d")
        n_clusters = result["cluster_id"][result["cluster_id"] >= 0].nunique()
        assert n_clusters == 1

    def test_empty_df(self):
        result = cluster_anomalies(pd.DataFrame(), epsilon=50)
        assert "cluster_id" in result.columns
        assert len(result) == 0


class TestComputeClusterMetrics:
    def test_metrics(self, clusterable_df):
        clustered = cluster_anomalies(clusterable_df, epsilon=50, mode="1d")
        metrics = compute_cluster_metrics(clustered)
        assert "anomaly_count" in metrics.columns
        assert "cluster_centroid_distance" in metrics.columns
        assert "cluster_span" in metrics.columns
        assert len(metrics) > 0

    def test_all_noise(self):
        df = pd.DataFrame({"cluster_id": [-1, -1], "distance_a": [100, 200]})
        metrics = compute_cluster_metrics(df)
        assert metrics.empty


class TestWriteClustersSummary:
    def test_writes_csv(self, clusterable_df, tmp_path):
        clustered = cluster_anomalies(clusterable_df, epsilon=50, mode="1d")
        metrics = compute_cluster_metrics(clustered)
        p = tmp_path / "clusters.csv"
        write_clusters_summary(metrics, p)
        assert p.exists()
