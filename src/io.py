"""
Data ingestion: read Excel/CSV, auto-detect column mapping, produce canonical schema.
"""

import logging
import os
import sys

import numpy as np
import pandas as pd

from .preprocess import clock_to_degrees, normalise_orientation, normalise_feature_type

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical schema columns (output of load_run)
# ---------------------------------------------------------------------------
CANONICAL_COLS = [
    "run_id",
    "feature_id",
    "distance",
    "joint_number",
    "relative_position",
    "clock_position_raw",
    "clock_deg",
    "feature_type_raw",
    "feature_type_norm",
    "orientation",
    "depth_percent",
    "length",
    "width",
    "wall_thickness",
]

# ---------------------------------------------------------------------------
# Column mapping configs per known vendor/year format
# ---------------------------------------------------------------------------

# Each mapping config is a dict: canonical_name -> list of possible raw column
# names (after lowercasing + whitespace normalisation).  The first match wins.
MAPPING_CONFIGS = {
    "2007_rosen": {
        "feature_id": ["j._no."],
        "distance": ["log_dist._[ft]"],
        "joint_number": ["j._no."],
        "relative_position": ["to_u/s_w._[ft]"],
        "clock_position_raw": ["o'clock"],
        "feature_type_raw": ["event"],
        "orientation": ["internal"],
        "depth_percent": ["depth_[%]"],
        "length": ["length_[in]"],
        "width": ["width_[in]"],
        "wall_thickness": ["t_[in]"],
    },
    "2015_baker": {
        "feature_id": ["j._no."],
        "distance": ["log_dist._[ft]"],
        "joint_number": ["j._no."],
        "relative_position": ["to_u/s_w._[ft]"],
        "clock_position_raw": ["o'clock"],
        "feature_type_raw": ["event_description"],
        "orientation": ["id/od"],
        "depth_percent": ["depth_[%]"],
        "length": ["length_[in]"],
        "width": ["width_[in]"],
        "wall_thickness": ["wt_[in]"],
    },
    "2022_entegra": {
        "feature_id": ["joint_number"],
        "distance": ["ili_wheel_count_[ft.]"],
        "joint_number": ["joint_number"],
        "relative_position": ["distance_to_u/s_gw_[ft]"],
        "clock_position_raw": ["o'clock_[hh:mm]"],
        "feature_type_raw": ["event_description"],
        "orientation": ["id/od"],
        "depth_percent": ["metal_loss_depth_[%]"],
        "length": ["length_[in]"],
        "width": ["width_[in]"],
        "wall_thickness": ["wt_[in]"],
    },
}


def _normalise_col_name(name: str) -> str:
    """Lowercase, strip, collapse whitespace/newlines to single underscore."""
    import re as _re
    s = name.strip().lower().replace("\n", " ").replace("\r", " ")
    s = s.replace(" ", "_")
    s = _re.sub(r"_+", "_", s)  # collapse consecutive underscores
    return s


def _score_mapping(df_cols: list[str], config: dict) -> int:
    """Count how many canonical fields a mapping config can resolve."""
    score = 0
    for canonical, candidates in config.items():
        for cand in candidates:
            if cand in df_cols:
                score += 1
                break
    return score


def auto_detect_mapping(df: pd.DataFrame) -> tuple[str, dict]:
    """Pick the best column mapping config for a DataFrame.

    Returns (config_name, resolved_mapping) where resolved_mapping is
    {canonical_name: actual_column_name}.
    """
    norm_cols = [_normalise_col_name(c) for c in df.columns]

    best_name = None
    best_score = -1
    best_resolved = {}

    for cfg_name, cfg in MAPPING_CONFIGS.items():
        score = _score_mapping(norm_cols, cfg)
        if score > best_score:
            best_score = score
            best_name = cfg_name
            # Build resolved mapping
            resolved = {}
            for canonical, candidates in cfg.items():
                for cand in candidates:
                    if cand in norm_cols:
                        # Map back to original column name
                        idx = norm_cols.index(cand)
                        resolved[canonical] = df.columns[idx]
                        break
            best_resolved = resolved

    log.info(
        "Auto-detected mapping config '%s' (score %d/%d)",
        best_name, best_score, len(MAPPING_CONFIGS.get(best_name, {})),
    )
    return best_name, best_resolved


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------

EXCEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm", ".xlsb")


def read_file(path: str, sheet_name: int | str = 0) -> pd.DataFrame:
    """Read a CSV or Excel file into a DataFrame."""
    ext = os.path.splitext(path)[1].lower()
    if ext in EXCEL_EXTENSIONS:
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Build canonical DataFrame
# ---------------------------------------------------------------------------

def _safe_numeric(series: pd.Series) -> pd.Series:
    """Coerce a series to numeric, returning NaN for failures."""
    return pd.to_numeric(series, errors="coerce")


def build_canonical(
    df: pd.DataFrame,
    run_id: str,
    mapping: dict[str, str],
) -> pd.DataFrame:
    """Transform a raw ILI DataFrame into the canonical schema.

    Args:
        df: raw DataFrame from vendor export.
        run_id: identifier for this run (e.g. "2015").
        mapping: {canonical_col: raw_col} resolved mapping.

    Returns:
        DataFrame with CANONICAL_COLS columns.
    """
    out = pd.DataFrame()
    out["run_id"] = run_id

    # Feature ID
    raw_id_col = mapping.get("feature_id")
    if raw_id_col and raw_id_col in df.columns:
        out["feature_id"] = df[raw_id_col].astype(str)
    else:
        # Generate synthetic IDs
        out["feature_id"] = [f"{run_id}_{i}" for i in range(len(df))]

    # Distance (required)
    raw_dist_col = mapping.get("distance")
    if raw_dist_col and raw_dist_col in df.columns:
        out["distance"] = _safe_numeric(df[raw_dist_col])
    else:
        log.error("No distance column found for run %s", run_id)
        sys.exit(1)

    # Joint number
    raw_jn_col = mapping.get("joint_number")
    if raw_jn_col and raw_jn_col in df.columns:
        out["joint_number"] = _safe_numeric(df[raw_jn_col])
    else:
        out["joint_number"] = np.nan

    # Relative position (distance to upstream weld)
    raw_rp_col = mapping.get("relative_position")
    if raw_rp_col and raw_rp_col in df.columns:
        out["relative_position"] = _safe_numeric(df[raw_rp_col])
    else:
        out["relative_position"] = np.nan

    # Clock position
    raw_clock_col = mapping.get("clock_position_raw")
    if raw_clock_col and raw_clock_col in df.columns:
        out["clock_position_raw"] = df[raw_clock_col]
        out["clock_deg"] = df[raw_clock_col].apply(clock_to_degrees)
    else:
        out["clock_position_raw"] = np.nan
        out["clock_deg"] = np.nan

    # Feature type
    raw_ft_col = mapping.get("feature_type_raw")
    if raw_ft_col and raw_ft_col in df.columns:
        out["feature_type_raw"] = df[raw_ft_col].astype(str)
        out["feature_type_norm"] = df[raw_ft_col].apply(normalise_feature_type)
    else:
        out["feature_type_raw"] = "unknown"
        out["feature_type_norm"] = "unknown"

    # Orientation
    raw_orient_col = mapping.get("orientation")
    if raw_orient_col and raw_orient_col in df.columns:
        out["orientation"] = df[raw_orient_col].apply(normalise_orientation)
    else:
        out["orientation"] = None

    # Depth percent
    raw_depth_col = mapping.get("depth_percent")
    if raw_depth_col and raw_depth_col in df.columns:
        out["depth_percent"] = _safe_numeric(df[raw_depth_col])
    else:
        out["depth_percent"] = np.nan

    # Length
    raw_len_col = mapping.get("length")
    if raw_len_col and raw_len_col in df.columns:
        out["length"] = _safe_numeric(df[raw_len_col])
    else:
        out["length"] = np.nan

    # Width
    raw_w_col = mapping.get("width")
    if raw_w_col and raw_w_col in df.columns:
        out["width"] = _safe_numeric(df[raw_w_col])
    else:
        out["width"] = np.nan

    # Wall thickness
    raw_wt_col = mapping.get("wall_thickness")
    if raw_wt_col and raw_wt_col in df.columns:
        out["wall_thickness"] = _safe_numeric(df[raw_wt_col])
    else:
        out["wall_thickness"] = np.nan

    return out


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_canonical(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Validate and clean a canonical DataFrame.

    - Drop rows with no distance.
    - Remove negative depth_percent.
    - Log warnings for data quality issues.
    """
    initial = len(df)

    # Must have a valid distance
    bad_dist = df["distance"].isna()
    if bad_dist.any():
        log.warning("%s: dropping %d rows with no distance", label, bad_dist.sum())
        df = df[~bad_dist].copy()

    # Negative depth
    neg_depth = df["depth_percent"] < 0
    if neg_depth.any():
        log.warning("%s: dropping %d rows with negative depth", label, neg_depth.sum())
        df = df[~neg_depth].copy()

    df = df.reset_index(drop=True)

    final = len(df)
    if final < initial:
        log.info("%s: validation reduced rows %d -> %d", label, initial, final)

    return df


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_run(
    path: str,
    run_id: str,
    sheet_name: int | str = 0,
) -> tuple[pd.DataFrame, dict]:
    """Load an ILI run from file, auto-detect mapping, return canonical DataFrame.

    Returns (canonical_df, mapping_info) where mapping_info is a dict
    with keys: config_name, resolved_mapping (for the alignment report).
    """
    if not os.path.isfile(path):
        log.error("File not found: %s", path)
        sys.exit(1)

    raw = read_file(path, sheet_name=sheet_name)
    log.info("Run %s: read %d rows from %s (sheet=%s)", run_id, len(raw), path, sheet_name)

    config_name, resolved = auto_detect_mapping(raw)
    log.info("Run %s: column mapping -> %s", run_id, resolved)

    canonical = build_canonical(raw, run_id, resolved)
    canonical = validate_canonical(canonical, f"Run {run_id}")

    mapping_info = {
        "config_name": config_name,
        "resolved_mapping": {k: v for k, v in resolved.items()},
        "raw_columns": list(raw.columns),
        "canonical_row_count": len(canonical),
    }

    # Summary stats
    n_anomalies = (canonical["feature_type_norm"] != "girth_weld").sum()
    n_welds = (canonical["feature_type_norm"] == "girth_weld").sum()
    log.info(
        "Run %s: %d total rows (%d anomalies, %d girth welds)",
        run_id, len(canonical), n_anomalies, n_welds,
    )

    return canonical, mapping_info
