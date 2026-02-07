"""
Anomaly matching: segment-wise Hungarian assignment with candidate gating.

Matches anomalies between Run A and aligned Run B using:
  1. Segment-wise processing (between consecutive matched control points)
  2. Candidate gating (distance, clock, type, orientation filters)
  3. Weighted cost function
  4. Hungarian (optimal) one-to-one assignment per segment
  5. Thresholding to flag UNCERTAIN matches and unmatched anomalies
"""

import logging

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from .preprocess import clock_distance, CONTROL_POINT_TYPES, COMPATIBLE_TYPES

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------
DEFAULT_DIST_TOL = 10.0       # feet
DEFAULT_CLOCK_TOL = 15.0      # degrees
DEFAULT_COST_THRESH = 15.0    # above this -> UNCERTAIN

# Cost function weights — depth and size weighted low because they're
# *expected* to change between runs (that's the growth we're measuring).
# Distance and clock are the primary matching signals.
DEFAULT_WEIGHTS = {
    "w_dist": 1.0,
    "w_clock": 0.5,
    "w_depth": 0.1,
    "w_size": 0.05,
    "type_penalty": 10.0,     # added when types differ but are "compatible"
}

# Large cost for infeasible pairs in the Hungarian matrix
BIG_COST = 1e6


# ---------------------------------------------------------------------------
# Feature type compatibility
# ---------------------------------------------------------------------------

def types_compatible(type_a: str, type_b: str) -> bool:
    """Check if two normalised feature types can be matched."""
    if type_a == type_b:
        return True
    # Check explicit compatibility map
    compat_a = COMPATIBLE_TYPES.get(type_a, {type_a})
    return type_b in compat_a


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------

def compute_pair_cost(
    row_a: pd.Series,
    row_b: pd.Series,
    weights: dict | None = None,
) -> float | None:
    """Compute matching cost between two anomalies.

    Returns None if the pair is infeasible (hard filter failure).
    Returns a float cost >= 0 otherwise.
    """
    w = weights or DEFAULT_WEIGHTS

    # --- Hard filters ---
    # Orientation must match (if both are known)
    orient_a = row_a.get("orientation")
    orient_b = row_b.get("orientation")
    if (
        orient_a is not None and orient_b is not None
        and isinstance(orient_a, str) and isinstance(orient_b, str)
        and orient_a != orient_b
    ):
        return None

    # Feature type must be compatible
    type_a = row_a["feature_type_norm"]
    type_b = row_b["feature_type_norm"]
    if not types_compatible(type_a, type_b):
        return None

    # --- Soft cost components ---
    # Distance (use corrected_distance for Run B if available)
    dist_a = row_a["distance"]
    dist_b = row_b.get("corrected_distance", row_b["distance"])
    delta_dist = abs(dist_a - dist_b)

    # Clock
    clock_a = row_a.get("clock_deg")
    clock_b = row_b.get("clock_deg")
    delta_clock = clock_distance(clock_a, clock_b)

    # Depth
    depth_a = row_a.get("depth_percent")
    depth_b = row_b.get("depth_percent")
    delta_depth = 0.0
    if pd.notna(depth_a) and pd.notna(depth_b):
        delta_depth = abs(depth_a - depth_b)

    # Size (length + width)
    delta_size = 0.0
    len_a = row_a.get("length")
    len_b = row_b.get("length")
    if pd.notna(len_a) and pd.notna(len_b):
        delta_size += abs(len_a - len_b)
    wid_a = row_a.get("width")
    wid_b = row_b.get("width")
    if pd.notna(wid_a) and pd.notna(wid_b):
        delta_size += abs(wid_a - wid_b)

    # Type penalty (non-zero only if types differ but are compatible)
    tp = 0.0 if type_a == type_b else w["type_penalty"]

    clock_contrib = 0.0
    if delta_clock is not None and not np.isnan(delta_clock):
        clock_contrib = delta_clock

    cost = (
        w["w_dist"] * delta_dist
        + w["w_clock"] * clock_contrib
        + w["w_depth"] * delta_depth
        + w["w_size"] * delta_size
        + tp
    )

    # Guard against NaN leaking into the cost matrix
    if np.isnan(cost):
        return None
    return cost


# ---------------------------------------------------------------------------
# Segment assignment
# ---------------------------------------------------------------------------

def _assign_segment(
    anomalies_a: pd.DataFrame,
    anomalies_b: pd.DataFrame,
    dist_tol: float,
    clock_tol: float,
    cost_thresh: float,
    weights: dict,
    segment_id: int,
) -> tuple[list[dict], list[int], list[int]]:
    """Run Hungarian matching on one segment.

    Returns (matched_pairs, unmatched_a_indices, unmatched_b_indices).
    Each matched pair is a dict with metadata.
    """
    n_a = len(anomalies_a)
    n_b = len(anomalies_b)

    if n_a == 0 or n_b == 0:
        return (
            [],
            list(anomalies_a.index),
            list(anomalies_b.index),
        )

    # Build sparse candidate list first for gating
    # candidates[i] = list of (j, cost) tuples
    candidates: dict[int, list[tuple[int, float]]] = {i: [] for i in range(n_a)}
    a_rows = list(anomalies_a.itertuples(index=True))
    b_rows = list(anomalies_b.itertuples(index=True))

    # Pre-extract arrays for fast distance gating
    a_dists = anomalies_a["distance"].values
    b_dists = (
        anomalies_b["corrected_distance"].values
        if "corrected_distance" in anomalies_b.columns
        else anomalies_b["distance"].values
    )
    a_clocks = anomalies_a["clock_deg"].values if "clock_deg" in anomalies_a.columns else None
    b_clocks = anomalies_b["clock_deg"].values if "clock_deg" in anomalies_b.columns else None

    for i in range(n_a):
        row_a = anomalies_a.iloc[i]
        for j in range(n_b):
            # Fast distance gate
            delta_d = abs(a_dists[i] - b_dists[j])
            if delta_d > dist_tol:
                continue

            # Fast clock gate
            if a_clocks is not None and b_clocks is not None:
                cd = clock_distance(
                    float(a_clocks[i]) if not np.isnan(a_clocks[i]) else None,
                    float(b_clocks[j]) if not np.isnan(b_clocks[j]) else None,
                )
                if cd is not None and cd > clock_tol:
                    continue

            # Full cost
            row_b = anomalies_b.iloc[j]
            cost = compute_pair_cost(row_a, row_b, weights)
            if cost is not None:
                candidates[i].append((j, cost))

    # Check if any candidates exist
    has_any = any(len(v) > 0 for v in candidates.values())
    if not has_any:
        return (
            [],
            list(anomalies_a.index),
            list(anomalies_b.index),
        )

    # Build local cost matrix for Hungarian
    # Size: n_a x n_b, filled with BIG_COST, then populated with real costs
    cost_matrix = np.full((n_a, n_b), BIG_COST)
    for i, cands in candidates.items():
        for j, c in cands:
            cost_matrix[i, j] = c

    # Solve assignment
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matched = []
    unmatched_a = set(range(n_a))
    unmatched_b = set(range(n_b))

    for i, j in zip(row_ind, col_ind):
        cost = cost_matrix[i, j]
        if cost >= BIG_COST:
            continue  # infeasible pair

        unmatched_a.discard(i)
        unmatched_b.discard(j)

        row_a = anomalies_a.iloc[i]
        row_b = anomalies_b.iloc[j]

        dist_b_col = "corrected_distance" if "corrected_distance" in anomalies_b.columns else "distance"
        delta_dist = abs(row_a["distance"] - row_b[dist_b_col])
        delta_clock = clock_distance(
            row_a.get("clock_deg"), row_b.get("clock_deg")
        )

        status = "UNCERTAIN" if cost > cost_thresh else "MATCHED"

        matched.append({
            "feature_id_a": row_a["feature_id"],
            "feature_id_b": row_b["feature_id"],
            "index_a": anomalies_a.index[i],
            "index_b": anomalies_b.index[j],
            "distance_a": row_a["distance"],
            "corrected_distance_b": row_b.get("corrected_distance", row_b["distance"]),
            "distance_b_raw": row_b["distance"],
            "delta_dist_ft": round(delta_dist, 4),
            "clock_deg_a": row_a.get("clock_deg"),
            "clock_deg_b": row_b.get("clock_deg"),
            "delta_clock_deg": round(delta_clock, 2) if delta_clock is not None else None,
            "feature_type": row_a["feature_type_norm"],
            "orientation": row_a.get("orientation"),
            "depth_pct_a": row_a.get("depth_percent"),
            "depth_pct_b": row_b.get("depth_percent"),
            "length_a": row_a.get("length"),
            "length_b": row_b.get("length"),
            "width_a": row_a.get("width"),
            "width_b": row_b.get("width"),
            "wall_thickness_a": row_a.get("wall_thickness"),
            "wall_thickness_b": row_b.get("wall_thickness"),
            "cost": round(cost, 4),
            "segment_id": segment_id,
            "status": status,
        })

    # Map back to original DataFrame indices
    unmatched_a_idx = [anomalies_a.index[i] for i in unmatched_a]
    unmatched_b_idx = [anomalies_b.index[j] for j in unmatched_b]

    return matched, unmatched_a_idx, unmatched_b_idx


# ---------------------------------------------------------------------------
# Segment-wise matching
# ---------------------------------------------------------------------------

def _get_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to matchable anomalies (exclude control points)."""
    return df[~df["feature_type_norm"].isin(CONTROL_POINT_TYPES)].copy()


def match_anomalies(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    matched_cp: pd.DataFrame,
    dist_tol: float = DEFAULT_DIST_TOL,
    clock_tol: float = DEFAULT_CLOCK_TOL,
    cost_thresh: float = DEFAULT_COST_THRESH,
    weights: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Segment-wise anomaly matching with Hungarian assignment.

    Divides the pipeline into segments between consecutive matched
    control points, then runs optimal matching within each segment.

    Args:
        df_a: canonical Run A DataFrame.
        df_b: aligned Run B DataFrame (with corrected_distance column).
        matched_cp: DataFrame of matched control point pairs (from alignment).
        dist_tol: max distance difference to consider a candidate.
        clock_tol: max clock difference in degrees.
        cost_thresh: cost above which a match is flagged UNCERTAIN.
        weights: cost function weight dict.

    Returns:
        (matched_df, missing_df, new_df)
        - matched_df: one row per matched pair with deltas and status.
        - missing_df: Run A anomalies with no match (MISSING).
        - new_df: Run B anomalies with no match (NEW).
    """
    w = weights or DEFAULT_WEIGHTS

    anom_a = _get_anomalies(df_a)
    anom_b = _get_anomalies(df_b)
    log.info("Matchable anomalies: Run A=%d, Run B=%d", len(anom_a), len(anom_b))

    # Build segment boundaries from matched control points
    cp = matched_cp.sort_values("distance_a").reset_index(drop=True)

    # Create segment boundaries: (-inf, cp0], (cp0, cp1], ..., (cpN, +inf)
    boundaries_a = [-np.inf] + list(cp["distance_a"]) + [np.inf]
    boundaries_b_corr = [-np.inf] + list(cp["distance_a"]) + [np.inf]
    # For Run B we use corrected_distance, which at control points ≈ distance_a

    all_matched = []
    all_unmatched_a = []
    all_unmatched_b = []

    n_segments = len(boundaries_a) - 1
    log.info("Processing %d segments", n_segments)

    for seg_idx in range(n_segments):
        lo = boundaries_a[seg_idx]
        hi = boundaries_a[seg_idx + 1]

        # Select anomalies in this segment
        seg_a = anom_a[(anom_a["distance"] > lo) & (anom_a["distance"] <= hi)]

        # For Run B, use corrected_distance for segmentation
        b_dist_col = "corrected_distance" if "corrected_distance" in anom_b.columns else "distance"
        seg_b = anom_b[(anom_b[b_dist_col] > lo) & (anom_b[b_dist_col] <= hi)]

        if len(seg_a) == 0 and len(seg_b) == 0:
            continue

        matched, um_a, um_b = _assign_segment(
            seg_a, seg_b, dist_tol, clock_tol, cost_thresh, w, seg_idx,
        )
        all_matched.extend(matched)
        all_unmatched_a.extend(um_a)
        all_unmatched_b.extend(um_b)

    # Build output DataFrames
    matched_df = pd.DataFrame(all_matched) if all_matched else pd.DataFrame()
    missing_df = df_a.loc[all_unmatched_a].copy() if all_unmatched_a else pd.DataFrame()
    new_df = df_b.loc[all_unmatched_b].copy() if all_unmatched_b else pd.DataFrame()

    # Add status columns to unmatched
    if not missing_df.empty:
        missing_df["status"] = "MISSING"
    if not new_df.empty:
        new_df["status"] = "NEW"

    # Summary
    n_matched = len(matched_df)
    n_uncertain = (matched_df["status"] == "UNCERTAIN").sum() if not matched_df.empty else 0
    n_confident = n_matched - n_uncertain
    log.info(
        "Matching complete: %d matched (%d confident, %d uncertain), "
        "%d missing (Run A only), %d new (Run B only)",
        n_matched, n_confident, n_uncertain, len(missing_df), len(new_df),
    )

    return matched_df, missing_df, new_df
