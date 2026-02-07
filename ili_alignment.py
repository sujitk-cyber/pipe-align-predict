"""
Pipeline ILI Data Alignment and Corrosion Growth Analysis

Reads two ILI run datasets (CSV or Excel), aligns them by distance, matches
anomalies between runs, computes corrosion growth rates, and outputs results.
"""

import argparse
import logging
import os
import re
import sys

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
DEFAULT_DISTANCE_THRESHOLD_FT = 10.0  # max feet apart to consider a match
DEFAULT_CLOCK_THRESHOLD_DEG = 15.0    # max degrees apart on circumference
DEFAULT_YEARS_BETWEEN_RUNS = 8.0

# Fields we expect (but handle gracefully if missing)
REQUIRED_FIELDS = ["feature_id", "distance", "feature_type", "depth_percent"]
OPTIONAL_FIELDS = ["clock_position", "orientation", "length", "width", "wall_thickness"]

# Common alternative column names found in ILI vendor reports.
# Maps normalised (lowercase, underscored) source names -> our canonical names.
COLUMN_ALIASES = {
    # distance
    "log_dist.": "distance",
    "log_dist._[ft]": "distance",
    "ili_wheel_count_[ft.]": "distance",
    # feature type / event
    "event": "feature_type",
    "event_description": "feature_type",
    # depth
    "depth_[%]": "depth_percent",
    "metal_loss_depth_[%]": "depth_percent",
    # clock position
    "o'clock": "clock_position",
    "o'clock_[hh:mm]": "clock_position",
    # orientation
    "id/od": "orientation",
    "internal": "orientation",
    # wall thickness
    "t_[in]": "wall_thickness",
    "wt_[in]": "wall_thickness",
    # length / width
    "length_[in]": "length",
    "width_[in]": "width",
    # joint number as feature_id fallback
    "j._no.": "feature_id",
    "joint_number": "feature_id",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clock_to_degrees(clock_value) -> float | None:
    """Convert a clock-position string like '4:30' or a numeric hour to degrees.

    12:00 (top-dead-centre) = 0°, increasing clockwise:
      3:00 = 90°, 6:00 = 180°, 9:00 = 270°.

    Accepts:
      - strings: "4:30", "12:00", "6"
      - numeric (int/float) treated as hours (e.g. 4.5 -> 135°)
      - datetime.time objects (common when reading Excel clock columns)
      - NaN / None -> None
    """
    import datetime

    if clock_value is None or (isinstance(clock_value, float) and np.isnan(clock_value)):
        return None

    # datetime.time from Excel (e.g. time(9, 30) -> 9:30)
    if isinstance(clock_value, datetime.time):
        hours = clock_value.hour + clock_value.minute / 60.0
    elif isinstance(clock_value, (int, float)):
        hours = float(clock_value)
    elif isinstance(clock_value, str):
        clock_value = clock_value.strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", clock_value)
        if m:
            hours = int(m.group(1)) + int(m.group(2)) / 60.0
        else:
            try:
                hours = float(clock_value)
            except ValueError:
                return None
    else:
        return None

    # Normalise to 0-12 range then convert to degrees
    hours = hours % 12.0
    return hours * 30.0  # 360° / 12 hours


def angular_difference(deg_a: float | None, deg_b: float | None) -> float | None:
    """Smallest angular difference on a 360° circle."""
    if deg_a is None or deg_b is None:
        return None
    diff = abs(deg_a - deg_b) % 360.0
    return min(diff, 360.0 - diff)


def normalise_orientation(val) -> str | None:
    """Map various orientation labels to 'ID' or 'OD' (or None)."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    s = str(val).strip().upper()
    if s in ("ID", "INTERNAL", "INT"):
        return "ID"
    if s in ("OD", "EXTERNAL", "EXT"):
        return "OD"
    return s  # keep whatever was provided so we can still compare


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

EXCEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm", ".xlsb")


def _read_file(path: str, sheet_name: int | str = 0) -> pd.DataFrame:
    """Read a CSV or Excel file into a DataFrame based on file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in EXCEL_EXTENSIONS:
        try:
            import openpyxl  # noqa: F401 – needed by pandas for .xlsx
        except ImportError:
            log.error(
                "openpyxl is required to read Excel files. "
                "Install it with: pip install openpyxl"
            )
            sys.exit(1)
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path)


def validate_dataframe(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Validate and clean an ILI run DataFrame.

    Checks performed:
      1. Required columns must be present.
      2. Duplicate feature_ids are removed (first occurrence kept).
      3. Rows with null required fields are dropped.
      4. depth_percent must be >= 0.
      5. clock_position (if present) is validated to 0-12 hour range.
      6. distance must be numeric and non-negative.
      7. Optional numeric fields get NaN where non-numeric.

    Returns the cleaned DataFrame (may have fewer rows than input).
    """
    initial_count = len(df)

    # --- Required columns ---
    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        log.error("%s is missing required columns: %s", label, missing)
        sys.exit(1)

    # --- Drop rows where required fields are null ---
    before = len(df)
    df = df.dropna(subset=REQUIRED_FIELDS)
    dropped = before - len(df)
    if dropped:
        log.warning("%s: dropped %d rows with null required fields", label, dropped)

    # --- Duplicate feature_ids ---
    dup_mask = df.duplicated(subset=["feature_id"], keep="first")
    n_dups = dup_mask.sum()
    if n_dups:
        dup_ids = df.loc[dup_mask, "feature_id"].tolist()
        log.warning(
            "%s: removed %d duplicate feature_id(s): %s",
            label, n_dups, dup_ids[:10],  # show first 10
        )
        df = df[~dup_mask]

    # --- depth_percent >= 0 ---
    df["depth_percent"] = pd.to_numeric(df["depth_percent"], errors="coerce")
    neg_depth = df["depth_percent"] < 0
    if neg_depth.any():
        log.warning(
            "%s: removed %d rows with negative depth_percent", label, neg_depth.sum(),
        )
        df = df[~neg_depth]

    # --- distance must be numeric and >= 0 ---
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    bad_dist = df["distance"].isna() | (df["distance"] < 0)
    if bad_dist.any():
        log.warning(
            "%s: removed %d rows with invalid distance", label, bad_dist.sum(),
        )
        df = df[~bad_dist]

    # --- clock_position validation (0-12 hour range) ---
    if "clock_position" in df.columns:
        def _valid_clock(val):
            deg = clock_to_degrees(val)
            if deg is None:
                return False
            # degrees should be 0-360 (corresponds to 0-12 hours); always true
            # after clock_to_degrees, but check the raw hour value is 0-12
            return True

        bad_clock = ~df["clock_position"].apply(_valid_clock)
        if bad_clock.any():
            log.warning(
                "%s: set %d unparseable clock_position values to NaN",
                label, bad_clock.sum(),
            )
            df.loc[bad_clock, "clock_position"] = np.nan

    # --- Coerce optional numeric fields ---
    for col in ("length", "width", "wall_thickness"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.reset_index(drop=True)

    final_count = len(df)
    if final_count < initial_count:
        log.info(
            "%s: validation reduced rows from %d to %d",
            label, initial_count, final_count,
        )

    return df


def load_run(path: str, label: str, sheet_name: int | str = 0) -> pd.DataFrame:
    """Read a CSV or Excel ILI run file, validate and clean it.

    Supports .csv, .xlsx, .xls, .xlsm, .xlsb.
    The *sheet_name* parameter is used only for Excel files (default: first sheet).
    """
    if not os.path.isfile(path):
        log.error("%s: file not found: %s", label, path)
        sys.exit(1)

    df = _read_file(path, sheet_name=sheet_name)

    # Normalise column names: lowercase, strip whitespace, underscores for spaces,
    # collapse newlines
    df.columns = [
        c.strip().lower().replace("\n", "_").replace(" ", "_") for c in df.columns
    ]

    # Apply column aliases so vendor-specific names map to our canonical fields
    rename_map = {}
    for col in df.columns:
        if col in COLUMN_ALIASES and COLUMN_ALIASES[col] not in df.columns:
            rename_map[col] = COLUMN_ALIASES[col]
    if rename_map:
        log.info("%s: mapped columns: %s", label, rename_map)
        df = df.rename(columns=rename_map)

    # Validate and clean
    df = validate_dataframe(df, label)

    present_optional = [f for f in OPTIONAL_FIELDS if f in df.columns]
    log.info(
        "%s: loaded %d anomalies from %s  |  optional fields: %s",
        label, len(df), os.path.basename(path), present_optional or "(none)",
    )
    return df


# ---------------------------------------------------------------------------
# Distance alignment
# ---------------------------------------------------------------------------

def compute_offset_from_welds(run1: pd.DataFrame, run2: pd.DataFrame) -> float:
    """Attempt to compute a constant distance offset using weld features.

    Looks for features whose feature_type contains 'weld' (case-insensitive)
    in both runs.  Uses the first weld found in each run to derive offset.
    Falls back to 0 if no welds are found.
    """
    weld_pat = re.compile(r"weld", re.IGNORECASE)

    welds1 = run1[run1["feature_type"].astype(str).str.contains(weld_pat, na=False)]
    welds2 = run2[run2["feature_type"].astype(str).str.contains(weld_pat, na=False)]

    if welds1.empty or welds2.empty:
        log.warning("No weld features found in one or both runs; offset = 0.0 ft")
        return 0.0

    welds1 = welds1.sort_values("distance")
    welds2 = welds2.sort_values("distance")

    offset = welds2.iloc[0]["distance"] - welds1.iloc[0]["distance"]
    log.info(
        "Weld-based offset: first weld Run1 @ %.2f ft, Run2 @ %.2f ft  ->  offset = %.2f ft",
        welds1.iloc[0]["distance"], welds2.iloc[0]["distance"], offset,
    )
    return offset


def align_run2(
    run1: pd.DataFrame,
    run2: pd.DataFrame,
    offset: float | None = None,
) -> pd.DataFrame:
    """Shift Run 2 distances into Run 1's coordinate frame.

    If *offset* is None it is computed automatically from weld references.
    Returns a copy of run2 with an 'aligned_distance' column.
    """
    if offset is None:
        offset = compute_offset_from_welds(run1, run2)

    run2 = run2.copy()
    run2["aligned_distance"] = run2["distance"] - offset
    log.info("Applied offset %.2f ft to Run 2 distances", offset)
    return run2


# ---------------------------------------------------------------------------
# Anomaly matching
# ---------------------------------------------------------------------------

def match_anomalies(
    run1: pd.DataFrame,
    run2: pd.DataFrame,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD_FT,
    clock_threshold_deg: float = DEFAULT_CLOCK_THRESHOLD_DEG,
) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    """Greedy one-to-one matching of Run 1 anomalies to Run 2 anomalies.

    Returns (matched_pairs, unmatched_run1, unmatched_run2).
    """
    has_clock = "clock_position" in run1.columns and "clock_position" in run2.columns
    has_orientation = "orientation" in run1.columns and "orientation" in run2.columns

    # Pre-compute clock degrees and normalised orientation
    r1 = run1.copy()
    r2 = run2.copy()

    if has_clock:
        r1["_clock_deg"] = r1["clock_position"].apply(clock_to_degrees)
        r2["_clock_deg"] = r2["clock_position"].apply(clock_to_degrees)
    if has_orientation:
        r1["_orient"] = r1["orientation"].apply(normalise_orientation)
        r2["_orient"] = r2["orientation"].apply(normalise_orientation)

    # Use aligned_distance for Run 2 if available
    r2_dist_col = "aligned_distance" if "aligned_distance" in r2.columns else "distance"

    available_r2 = set(r2.index)  # track which Run 2 rows are still available
    matched: list[dict] = []
    unmatched_r1_indices: list[int] = []

    for idx1, row1 in r1.iterrows():
        best_idx2 = None
        best_score = float("inf")

        for idx2 in list(available_r2):
            row2 = r2.loc[idx2]

            # ---- Hard filters ----
            # Orientation must match (if available)
            if has_orientation:
                o1 = row1["_orient"]
                o2 = row2["_orient"]
                if o1 is not None and o2 is not None and o1 != o2:
                    continue

            # Feature type must match
            t1 = str(row1["feature_type"]).strip().lower()
            t2 = str(row2["feature_type"]).strip().lower()
            if t1 != t2:
                continue

            # Distance within threshold
            dist_diff = abs(row1["distance"] - row2[r2_dist_col])
            if dist_diff > distance_threshold:
                continue

            # Clock within threshold (if available)
            clock_diff = None
            if has_clock:
                clock_diff = angular_difference(row1["_clock_deg"], row2["_clock_deg"])
                if clock_diff is not None and clock_diff > clock_threshold_deg:
                    continue

            # ---- Scoring (lower is better) ----
            score = dist_diff
            if clock_diff is not None:
                # Weight clock difference: 1 degree ~ 0.1 ft for scoring
                score += clock_diff * 0.1

            if score < best_score:
                best_score = score
                best_idx2 = idx2

        if best_idx2 is not None:
            available_r2.discard(best_idx2)
            matched.append({
                "run1_index": idx1,
                "run2_index": best_idx2,
                "distance_diff_ft": abs(row1["distance"] - r2.loc[best_idx2, r2_dist_col]),
            })
        else:
            unmatched_r1_indices.append(idx1)

    unmatched_r1 = r1.loc[unmatched_r1_indices].drop(
        columns=[c for c in ("_clock_deg", "_orient") if c in r1.columns],
    )
    unmatched_r2 = r2.loc[sorted(available_r2)].drop(
        columns=[c for c in ("_clock_deg", "_orient") if c in r2.columns],
    )

    log.info(
        "Matching complete: %d matched, %d unmatched in Run 1, %d unmatched in Run 2",
        len(matched), len(unmatched_r1), len(unmatched_r2),
    )
    return matched, unmatched_r1, unmatched_r2


# ---------------------------------------------------------------------------
# Growth-rate calculation
# ---------------------------------------------------------------------------

def compute_growth(
    matched_pairs: list[dict],
    run1: pd.DataFrame,
    run2: pd.DataFrame,
    years: float,
) -> pd.DataFrame:
    """Build a DataFrame of growth-rate results for each matched pair."""
    has_length = "length" in run1.columns and "length" in run2.columns
    has_width = "width" in run1.columns and "width" in run2.columns
    has_wt = "wall_thickness" in run1.columns and "wall_thickness" in run2.columns

    r2_dist_col = "aligned_distance" if "aligned_distance" in run2.columns else "distance"

    records = []
    for pair in matched_pairs:
        r1 = run1.loc[pair["run1_index"]]
        r2 = run2.loc[pair["run2_index"]]

        depth1 = r1["depth_percent"]
        depth2 = r2["depth_percent"]
        depth_change = depth2 - depth1
        depth_rate = depth_change / years if years > 0 else np.nan

        rec = {
            "feature_id_run1": r1["feature_id"],
            "feature_id_run2": r2["feature_id"],
            "feature_type": r1["feature_type"],
            "aligned_distance_ft": r1["distance"],
            "distance_diff_ft": pair["distance_diff_ft"],
            "depth_pct_run1": depth1,
            "depth_pct_run2": depth2,
            "depth_change_pct": depth_change,
            "depth_rate_pct_per_yr": round(depth_rate, 4),
        }

        if has_wt:
            wt = r1["wall_thickness"]
            if pd.notna(wt) and wt > 0:
                rec["depth_mils_run1"] = round(depth1 / 100.0 * wt * 1000, 1)
                rec["depth_mils_run2"] = round(depth2 / 100.0 * wt * 1000, 1)
                rec["depth_change_mils"] = round(depth_change / 100.0 * wt * 1000, 1)
                rec["depth_rate_mils_per_yr"] = round(
                    depth_change / 100.0 * wt * 1000 / years if years > 0 else np.nan, 2,
                )

        if has_length:
            len1 = r1["length"]
            len2 = r2["length"]
            if pd.notna(len1) and pd.notna(len2):
                rec["length_in_run1"] = len1
                rec["length_in_run2"] = len2
                rec["length_change_in"] = round(len2 - len1, 3)
                rec["length_rate_in_per_yr"] = round(
                    (len2 - len1) / years if years > 0 else np.nan, 4,
                )

        if has_width:
            w1 = r1["width"]
            w2 = r2["width"]
            if pd.notna(w1) and pd.notna(w2):
                rec["width_in_run1"] = w1
                rec["width_in_run2"] = w2
                rec["width_change_in"] = round(w2 - w1, 3)
                rec["width_rate_in_per_yr"] = round(
                    (w2 - w1) / years if years > 0 else np.nan, 4,
                )

        records.append(rec)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def print_sample_matches(growth_df: pd.DataFrame, n: int = 5) -> None:
    """Print a few example matches for quick verification."""
    sample = growth_df.head(n)
    log.info("--- Sample matched anomalies (up to %d) ---", n)
    for _, row in sample.iterrows():
        parts = [
            f"  Run1 {row['feature_id_run1']} <-> Run2 {row['feature_id_run2']}",
            f"  dist_diff={row['distance_diff_ft']:.2f} ft",
            f"  depth {row['depth_pct_run1']:.1f}% -> {row['depth_pct_run2']:.1f}%",
            f"  rate={row['depth_rate_pct_per_yr']:.4f} %/yr",
        ]
        log.info(" | ".join(parts))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ILI Run Alignment & Corrosion Growth Analysis",
    )
    parser.add_argument("run1", help="Path to Run 1 data file (CSV or Excel)")
    parser.add_argument("run2", help="Path to Run 2 data file (CSV or Excel)")
    parser.add_argument(
        "--sheet", default=0,
        help="Sheet name or index for Excel files (default: first sheet)",
    )
    parser.add_argument(
        "--years", type=float, default=DEFAULT_YEARS_BETWEEN_RUNS,
        help=f"Years between inspections (default: {DEFAULT_YEARS_BETWEEN_RUNS})",
    )
    parser.add_argument(
        "--distance-threshold", type=float, default=DEFAULT_DISTANCE_THRESHOLD_FT,
        help=f"Max distance (ft) for matching (default: {DEFAULT_DISTANCE_THRESHOLD_FT})",
    )
    parser.add_argument(
        "--clock-threshold", type=float, default=DEFAULT_CLOCK_THRESHOLD_DEG,
        help=f"Max clock-position diff in degrees (default: {DEFAULT_CLOCK_THRESHOLD_DEG})",
    )
    parser.add_argument(
        "--offset", type=float, default=None,
        help="Manual distance offset (ft) to apply to Run 2. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--output-dir", default=".",
        help="Directory for output CSV files (default: current directory)",
    )
    args = parser.parse_args()

    # Step 1: Load data
    log.info("=" * 60)
    log.info("Step 1: Loading ILI run data")
    log.info("=" * 60)
    # Resolve sheet arg: try int conversion for numeric sheet indices
    sheet = args.sheet
    try:
        sheet = int(sheet)
    except (ValueError, TypeError):
        pass

    run1 = load_run(args.run1, "Run 1", sheet_name=sheet)
    run2 = load_run(args.run2, "Run 2", sheet_name=sheet)

    # Step 2: Align distances
    log.info("=" * 60)
    log.info("Step 2: Aligning Run 2 distances to Run 1 coordinate frame")
    log.info("=" * 60)
    run2 = align_run2(run1, run2, offset=args.offset)

    # Step 3: Match anomalies
    log.info("=" * 60)
    log.info("Step 3: Matching anomalies between runs")
    log.info("=" * 60)
    matched_pairs, unmatched_r1, unmatched_r2 = match_anomalies(
        run1, run2,
        distance_threshold=args.distance_threshold,
        clock_threshold_deg=args.clock_threshold,
    )

    # Step 4: Compute growth rates
    log.info("=" * 60)
    log.info("Step 4: Computing corrosion growth rates")
    log.info("=" * 60)
    growth_df = compute_growth(matched_pairs, run1, run2, args.years)
    log.info("Growth rates computed for %d matched anomaly pairs", len(growth_df))

    if not growth_df.empty:
        print_sample_matches(growth_df)

    # Step 5: Write outputs
    log.info("=" * 60)
    log.info("Step 5: Writing output files")
    log.info("=" * 60)
    out = args.output_dir

    matched_path = f"{out}/matched_anomalies.csv"
    growth_df.to_csv(matched_path, index=False)
    log.info("Wrote %d rows to %s", len(growth_df), matched_path)

    unmatched_r1_path = f"{out}/unmatched_run1.csv"
    unmatched_r1.to_csv(unmatched_r1_path, index=False)
    log.info("Wrote %d rows to %s", len(unmatched_r1), unmatched_r1_path)

    unmatched_r2_path = f"{out}/unmatched_run2.csv"
    unmatched_r2.to_csv(unmatched_r2_path, index=False)
    log.info("Wrote %d rows to %s", len(unmatched_r2), unmatched_r2_path)

    # Summary
    log.info("=" * 60)
    log.info("Summary")
    log.info("=" * 60)
    log.info("Run 1 anomalies:       %d", len(run1))
    log.info("Run 2 anomalies:       %d", len(run2))
    log.info("Matched pairs:         %d", len(growth_df))
    log.info("Unmatched in Run 1:    %d  (missing from Run 2)", len(unmatched_r1))
    log.info("Unmatched in Run 2:    %d  (new in Run 2)", len(unmatched_r2))

    if not growth_df.empty:
        log.info("Avg depth growth rate: %.4f %%/yr", growth_df["depth_rate_pct_per_yr"].mean())
        log.info("Max depth growth rate: %.4f %%/yr", growth_df["depth_rate_pct_per_yr"].max())


if __name__ == "__main__":
    main()
