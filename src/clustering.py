"""
Anomaly clustering using DBSCAN to identify interaction zones.

Groups spatially close anomalies that may interact, computes per-cluster
aggregated metrics, and appends cluster_id to matched results.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

log = logging.getLogger(__name__)

DEFAULT_EPSILON = 50.0  # feet (1D distance threshold)
DEFAULT_MIN_SAMPLES = 2


def cluster_anomalies(
    matched_df: pd.DataFrame,
    epsilon: float = DEFAULT_EPSILON,
    mode: str = "1d",
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> pd.DataFrame:
    """Assign cluster_id to matched anomalies using DBSCAN.

    Args:
        matched_df: matched anomaly DataFrame with distance and clock columns.
        epsilon: DBSCAN neighbourhood radius (feet for 1D, combined for 2D).
        mode: '1d' uses distance only; '2d' uses (distance, normalised_clock).
        min_samples: minimum cluster size for DBSCAN.

    Returns:
        Copy of matched_df with 'cluster_id' column added (-1 = noise/unclustered).
    """
    df = matched_df.copy()

    if df.empty:
        df["cluster_id"] = pd.Series(dtype=int)
        return df

    dist_col = "distance_a" if "distance_a" in df.columns else "distance"
    distances = pd.to_numeric(df[dist_col], errors="coerce").fillna(0).values

    if mode == "2d" and "clock_deg_a" in df.columns:
        clock = pd.to_numeric(df["clock_deg_a"], errors="coerce").fillna(180).values
        # Normalise clock to [0, 1] range scaled by epsilon so both dimensions
        # contribute roughly equally (360 deg -> epsilon range)
        clock_norm = (clock / 360.0) * epsilon
        X = np.column_stack([distances, clock_norm])
    else:
        X = distances.reshape(-1, 1)

    db = DBSCAN(eps=epsilon, min_samples=min_samples, metric="euclidean")
    labels = db.fit_predict(X)

    df["cluster_id"] = labels.astype(int)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    log.info(
        "Clustering (%s, eps=%.1f): %d clusters, %d unclustered anomalies",
        mode, epsilon, n_clusters, n_noise,
    )

    return df


def compute_cluster_metrics(clustered_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-cluster aggregated metrics.

    Metrics per cluster:
        anomaly_count, cluster_centroid_distance, cluster_span,
        average_depth, total_metal_loss_area, cluster_growth_rate.

    Args:
        clustered_df: DataFrame with cluster_id column.

    Returns:
        DataFrame with one row per cluster (excludes noise cluster -1).
    """
    df = clustered_df[clustered_df["cluster_id"] >= 0].copy()

    if df.empty:
        return pd.DataFrame()

    dist_col = "distance_a" if "distance_a" in df.columns else "distance"

    groups = df.groupby("cluster_id")

    metrics = pd.DataFrame({
        "anomaly_count": groups.size(),
        "cluster_centroid_distance": groups[dist_col].mean(),
        "cluster_span": groups[dist_col].apply(lambda s: s.max() - s.min()),
    })

    # Average depth
    if "depth_pct_b" in df.columns:
        metrics["average_depth"] = groups["depth_pct_b"].mean()

    # Total metal loss area (length * width summed)
    if "length_b" in df.columns and "width_b" in df.columns:
        df["_area"] = pd.to_numeric(df["length_b"], errors="coerce").fillna(0) * \
                       pd.to_numeric(df["width_b"], errors="coerce").fillna(0)
        metrics["total_metal_loss_area"] = df.groupby("cluster_id")["_area"].sum()

    # Weighted average growth rate
    if "depth_growth_pct_per_yr" in df.columns:
        metrics["cluster_growth_rate"] = groups["depth_growth_pct_per_yr"].mean()

    metrics = metrics.reset_index()

    # Round
    for col in metrics.select_dtypes(include="float").columns:
        metrics[col] = metrics[col].round(4)

    log.info("Computed metrics for %d clusters", len(metrics))
    return metrics


def write_clusters_summary(metrics_df: pd.DataFrame, path) -> None:
    """Write cluster metrics to CSV.

    Args:
        metrics_df: output from compute_cluster_metrics.
        path: output file path.
    """
    if metrics_df.empty:
        log.info("No clusters to write")
        return
    metrics_df.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote cluster summary to %s", path)
