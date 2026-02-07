"""
Distance alignment: control point identification, matching, and piecewise
linear correction of Run B distances into Run A's coordinate frame.
"""

import logging

import numpy as np
import pandas as pd

from .preprocess import CONTROL_POINT_TYPES

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Control point extraction
# ---------------------------------------------------------------------------

def extract_control_points(
    df: pd.DataFrame,
    types: set[str] | None = None,
) -> pd.DataFrame:
    """Extract rows that represent fixed pipeline features (control points).

    Args:
        df: canonical DataFrame from io.load_run.
        types: which feature_type_norm values count as control points.
               Defaults to CONTROL_POINT_TYPES.

    Returns:
        DataFrame subset sorted by distance, with original index preserved.
    """
    if types is None:
        types = CONTROL_POINT_TYPES

    mask = df["feature_type_norm"].isin(types)
    cp = df[mask].sort_values("distance").copy()
    log.info(
        "Extracted %d control points (%s)",
        len(cp),
        cp["feature_type_norm"].value_counts().to_dict(),
    )
    return cp


# ---------------------------------------------------------------------------
# Control point matching
# ---------------------------------------------------------------------------

def match_control_points_by_joint(
    cp_a: pd.DataFrame,
    cp_b: pd.DataFrame,
    type_filter: str = "girth_weld",
) -> pd.DataFrame:
    """Match control points between two runs using joint_number.

    Only considers features of *type_filter* (default: girth_weld) because
    non-weld features sharing a joint number aren't reliable 1:1 matches.

    Returns a DataFrame with columns:
        joint_number, distance_a, distance_b, feature_type
    sorted by distance_a.
    """
    # Filter to the specific type and rows with joint numbers
    a = cp_a[
        (cp_a["joint_number"].notna()) & (cp_a["feature_type_norm"] == type_filter)
    ].copy()
    b = cp_b[
        (cp_b["joint_number"].notna()) & (cp_b["feature_type_norm"] == type_filter)
    ].copy()

    if a.empty or b.empty:
        log.warning("No %s with joint numbers for matching", type_filter)
        return pd.DataFrame()

    # Ensure joint_number is the same dtype for merge
    a["joint_number"] = a["joint_number"].astype(int)
    b["joint_number"] = b["joint_number"].astype(int)

    # Drop duplicate joint numbers within each run (keep first by distance)
    a = a.sort_values("distance").drop_duplicates(subset="joint_number", keep="first")
    b = b.sort_values("distance").drop_duplicates(subset="joint_number", keep="first")

    # Merge on joint_number — inner join gives matched pairs
    merged = a.merge(
        b,
        on="joint_number",
        suffixes=("_a", "_b"),
        how="inner",
    )

    result = pd.DataFrame({
        "joint_number": merged["joint_number"],
        "distance_a": merged["distance_a"],
        "distance_b": merged["distance_b"],
        "feature_type": type_filter,
    }).sort_values("distance_a").reset_index(drop=True)

    log.info("Matched %d %s by joint_number", len(result), type_filter)
    return result


def match_control_points_by_sequence(
    cp_a: pd.DataFrame,
    cp_b: pd.DataFrame,
    type_filter: str = "girth_weld",
    max_spacing_diff_pct: float = 0.20,
) -> pd.DataFrame:
    """Fallback: match control points by ordered sequence and spacing.

    Filters both runs to a single feature type (default: girth_weld),
    sorts by distance, and pairs them in order. Rejects pairs where
    the inter-weld spacing differs by more than max_spacing_diff_pct.

    Returns same schema as match_control_points_by_joint.
    """
    a = cp_a[cp_a["feature_type_norm"] == type_filter].sort_values("distance").reset_index()
    b = cp_b[cp_b["feature_type_norm"] == type_filter].sort_values("distance").reset_index()

    n = min(len(a), len(b))
    if n == 0:
        log.warning("No %s features for sequence-based matching", type_filter)
        return pd.DataFrame()

    # Pair by ordinal position
    records = []
    rejected = 0
    for i in range(n):
        rec = {
            "joint_number": a.iloc[i].get("joint_number", np.nan),
            "distance_a": a.iloc[i]["distance"],
            "distance_b": b.iloc[i]["distance"],
            "feature_type": type_filter,
            "index_a": a.iloc[i]["index"],
            "index_b": b.iloc[i]["index"],
        }
        # Validate spacing consistency (skip first pair)
        if i > 0 and len(records) > 0:
            spacing_a = rec["distance_a"] - records[-1]["distance_a"]
            spacing_b = rec["distance_b"] - records[-1]["distance_b"]
            if spacing_a > 0:
                diff_pct = abs(spacing_b - spacing_a) / spacing_a
                if diff_pct > max_spacing_diff_pct:
                    rejected += 1
                    continue
        records.append(rec)

    if rejected:
        log.warning(
            "Sequence matching: rejected %d pairs with spacing diff > %.0f%%",
            rejected, max_spacing_diff_pct * 100,
        )

    result = pd.DataFrame(records).sort_values("distance_a").reset_index(drop=True)
    log.info("Matched %d control points by sequence (%s)", len(result), type_filter)
    return result


def match_control_points(
    cp_a: pd.DataFrame,
    cp_b: pd.DataFrame,
) -> pd.DataFrame:
    """Match control points using best available method.

    Tries joint_number first; falls back to sequence matching if
    fewer than 2 joint-based matches are found.
    """
    matched = match_control_points_by_joint(cp_a, cp_b)

    if len(matched) >= 2:
        return matched

    log.info("Joint-based matching insufficient (%d); falling back to sequence", len(matched))
    return match_control_points_by_sequence(cp_a, cp_b)
