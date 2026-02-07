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


# ---------------------------------------------------------------------------
# Piecewise linear alignment
# ---------------------------------------------------------------------------

def compute_piecewise_transforms(
    matched_cp: pd.DataFrame,
) -> list[dict]:
    """Compute per-segment scale and shift from matched control points.

    For consecutive matched control point pairs (i, i+1):
        scale = (a1 - a0) / (b1 - b0)
        shift = a0 - scale * b0

    So: corrected_b = scale * distance_b + shift

    Returns a list of segment dicts:
        {seg_id, a_start, a_end, b_start, b_end, scale, shift}

    The first segment extends from -inf to the first control point,
    and the last segment extends from the last control point to +inf
    (both using the nearest segment's transform).
    """
    if len(matched_cp) < 2:
        # Fallback: global affine from single point or no points
        if len(matched_cp) == 1:
            shift = matched_cp.iloc[0]["distance_a"] - matched_cp.iloc[0]["distance_b"]
            log.warning("Only 1 control point — using constant offset %.2f ft", shift)
            return [{
                "seg_id": 0,
                "a_start": -np.inf, "a_end": np.inf,
                "b_start": -np.inf, "b_end": np.inf,
                "scale": 1.0, "shift": shift,
            }]
        else:
            log.warning("No control points matched — no alignment applied")
            return [{
                "seg_id": 0,
                "a_start": -np.inf, "a_end": np.inf,
                "b_start": -np.inf, "b_end": np.inf,
                "scale": 1.0, "shift": 0.0,
            }]

    segments = []
    cp = matched_cp.sort_values("distance_a").reset_index(drop=True)

    for i in range(len(cp) - 1):
        a0, a1 = cp.iloc[i]["distance_a"], cp.iloc[i + 1]["distance_a"]
        b0, b1 = cp.iloc[i]["distance_b"], cp.iloc[i + 1]["distance_b"]

        span_b = b1 - b0
        if abs(span_b) < 1e-9:
            # Degenerate segment — use offset only
            scale = 1.0
            shift = a0 - b0
        else:
            scale = (a1 - a0) / span_b
            shift = a0 - scale * b0

        segments.append({
            "seg_id": i,
            "a_start": a0,
            "a_end": a1,
            "b_start": b0,
            "b_end": b1,
            "scale": round(scale, 8),
            "shift": round(shift, 4),
        })

    log.info("Computed %d piecewise segments", len(segments))
    return segments


def apply_alignment(
    df_b: pd.DataFrame,
    segments: list[dict],
    matched_cp: pd.DataFrame,
) -> pd.DataFrame:
    """Apply piecewise linear correction to Run B distances.

    For each row in df_b, finds the appropriate segment and applies:
        corrected_distance = scale * distance + shift

    Rows before the first control point use the first segment's transform.
    Rows after the last control point use the last segment's transform.

    Adds 'corrected_distance' column to a copy of df_b.
    """
    df = df_b.copy()
    distances = df["distance"].values
    corrected = np.empty_like(distances, dtype=float)

    if not segments:
        corrected[:] = distances
        df["corrected_distance"] = corrected
        return df

    # Build sorted arrays of segment boundaries (in Run B space)
    seg_b_starts = np.array([s["b_start"] for s in segments])

    for i, d in enumerate(distances):
        # Find which segment this distance falls in
        # Use the last segment whose b_start <= d
        idx = np.searchsorted(seg_b_starts, d, side="right") - 1
        idx = max(0, min(idx, len(segments) - 1))

        seg = segments[idx]
        corrected[i] = seg["scale"] * d + seg["shift"]

    df["corrected_distance"] = np.round(corrected, 4)
    return df


def compute_residuals(
    matched_cp: pd.DataFrame,
    segments: list[dict],
) -> pd.DataFrame:
    """Compute alignment residuals at each matched control point.

    Residual = corrected_distance_b - distance_a (should be ~0 for good alignment).
    """
    cp = matched_cp.copy()
    seg_b_starts = np.array([s["b_start"] for s in segments])

    residuals = []
    for _, row in cp.iterrows():
        d_b = row["distance_b"]
        idx = max(0, min(np.searchsorted(seg_b_starts, d_b, side="right") - 1, len(segments) - 1))
        seg = segments[idx]
        corrected = seg["scale"] * d_b + seg["shift"]
        residuals.append(corrected - row["distance_a"])

    cp["residual_ft"] = np.round(residuals, 6)
    return cp


# ---------------------------------------------------------------------------
# High-level alignment pipeline
# ---------------------------------------------------------------------------

def align_runs(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    cp_types: set[str] | None = None,
) -> tuple[pd.DataFrame, list[dict], pd.DataFrame, pd.DataFrame]:
    """Full alignment pipeline: extract control points, match, align.

    Args:
        df_a: canonical DataFrame for Run A (reference).
        df_b: canonical DataFrame for Run B (to be corrected).
        cp_types: which feature types to use as control points.

    Returns:
        (df_b_aligned, segments, matched_cp, residuals)
        - df_b_aligned: Run B with 'corrected_distance' column added.
        - segments: list of piecewise transform dicts.
        - matched_cp: DataFrame of matched control point pairs.
        - residuals: matched_cp with residual_ft column.
    """
    log.info("--- Alignment: extracting control points ---")
    cp_a = extract_control_points(df_a, types=cp_types)
    cp_b = extract_control_points(df_b, types=cp_types)

    log.info("--- Alignment: matching control points ---")
    matched_cp = match_control_points(cp_a, cp_b)

    if matched_cp.empty:
        log.error("No control points could be matched — alignment not possible")
        df_b_out = df_b.copy()
        df_b_out["corrected_distance"] = df_b_out["distance"]
        return df_b_out, [], matched_cp, pd.DataFrame()

    log.info("--- Alignment: computing piecewise transforms ---")
    segments = compute_piecewise_transforms(matched_cp)

    log.info("--- Alignment: applying correction to Run B ---")
    df_b_aligned = apply_alignment(df_b, segments, matched_cp)

    log.info("--- Alignment: computing residuals ---")
    residuals = compute_residuals(matched_cp, segments)

    # Summary stats
    max_residual = residuals["residual_ft"].abs().max()
    mean_residual = residuals["residual_ft"].abs().mean()
    log.info(
        "Alignment complete: %d segments, %d control points matched, "
        "max residual=%.4f ft, mean residual=%.4f ft",
        len(segments), len(matched_cp), max_residual, mean_residual,
    )

    return df_b_aligned, segments, matched_cp, residuals
