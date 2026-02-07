"""
Multi-run anomaly tracking across 3+ inspection runs.

Builds anomaly tracks by chaining pairwise matches across consecutive run
pairs, assigning a unique track_id to each physical anomaly, and outputting
tracks_multi_run.csv with per-run measurements.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .io import load_run
from .alignment import align_runs
from .matching import match_anomalies
from .growth import multi_run_growth_analysis, detect_acceleration

log = logging.getLogger(__name__)


def _build_pair_matches(
    file_path: str,
    run_specs: list[dict],
    dist_tol: float,
    clock_tol: float,
    cost_thresh: float,
) -> list[pd.DataFrame]:
    """Load runs and build pairwise matched DataFrames for consecutive pairs.

    Args:
        file_path: path to data file (Excel or CSV).
        run_specs: list of dicts with keys 'sheet', 'run_id'.
        dist_tol, clock_tol, cost_thresh: matching parameters.

    Returns:
        List of matched DataFrames for pairs (0-1), (1-2), ...
    """
    dfs = []
    for spec in run_specs:
        df, _ = load_run(file_path, spec["run_id"], sheet_name=spec["sheet"])
        dfs.append(df)

    pair_matches = []
    for i in range(len(dfs) - 1):
        df_a, df_b = dfs[i], dfs[i + 1]
        df_b_aligned, _, matched_cp, _ = align_runs(df_a, df_b)
        matched_df, _, _ = match_anomalies(
            df_a, df_b_aligned, matched_cp,
            dist_tol=dist_tol, clock_tol=clock_tol, cost_thresh=cost_thresh,
        )
        matched_df["pair_idx"] = i
        pair_matches.append(matched_df)
        log.info(
            "Pair %s -> %s: %d matches",
            run_specs[i]["run_id"], run_specs[i + 1]["run_id"], len(matched_df),
        )

    return pair_matches


def build_tracks(
    pair_matches: list[pd.DataFrame],
    run_ids: list[str],
) -> pd.DataFrame:
    """Chain pairwise matches into multi-run tracks.

    Each track represents one physical anomaly observed across multiple runs.

    Args:
        pair_matches: list of pairwise matched DataFrames.
        run_ids: ordered list of run identifiers.

    Returns:
        DataFrame with columns: track_id, plus per-run feature_id and depth columns.
    """
    # Start with first pair — each matched pair starts a track
    tracks = {}  # track_id -> dict of {run_id: feature_id, ...}
    next_track_id = 0

    if not pair_matches or pair_matches[0].empty:
        return pd.DataFrame()

    # First pair: seed tracks
    first = pair_matches[0]
    for _, row in first.iterrows():
        tracks[next_track_id] = {
            f"feature_id_{run_ids[0]}": row.get("feature_id_a"),
            f"feature_id_{run_ids[1]}": row.get("feature_id_b"),
            f"depth_{run_ids[0]}": row.get("depth_pct_a"),
            f"depth_{run_ids[1]}": row.get("depth_pct_b"),
            f"distance_{run_ids[0]}": row.get("distance_a"),
        }
        next_track_id += 1

    # Chain subsequent pairs
    for pair_idx in range(1, len(pair_matches)):
        if pair_matches[pair_idx].empty:
            continue

        run_b_id = run_ids[pair_idx + 1]
        run_a_id = run_ids[pair_idx]

        # Build lookup: feature_id_a (this pair's A) -> row
        for _, row in pair_matches[pair_idx].iterrows():
            fid_a = row.get("feature_id_a")
            fid_b = row.get("feature_id_b")

            # Find existing track where the previous run's feature_id matches
            found = False
            prev_fid_key = f"feature_id_{run_a_id}"
            for tid, track in tracks.items():
                if track.get(prev_fid_key) == fid_a:
                    track[f"feature_id_{run_b_id}"] = fid_b
                    track[f"depth_{run_b_id}"] = row.get("depth_pct_b")
                    found = True
                    break

            if not found:
                # New track starting from this pair
                tracks[next_track_id] = {
                    f"feature_id_{run_a_id}": fid_a,
                    f"feature_id_{run_b_id}": fid_b,
                    f"depth_{run_a_id}": row.get("depth_pct_a"),
                    f"depth_{run_b_id}": row.get("depth_pct_b"),
                }
                next_track_id += 1

    # Convert to DataFrame
    records = []
    for tid, track in tracks.items():
        track["track_id"] = tid
        track["n_detections"] = sum(
            1 for k, v in track.items()
            if k.startswith("feature_id_") and v is not None
        )
        records.append(track)

    result = pd.DataFrame(records)
    if not result.empty:
        # Reorder columns
        cols = ["track_id", "n_detections"] + sorted(
            [c for c in result.columns if c not in ("track_id", "n_detections")]
        )
        result = result[[c for c in cols if c in result.columns]]

    log.info("Built %d anomaly tracks across %d runs", len(result), len(run_ids))
    return result


def write_tracks_csv(tracks_df: pd.DataFrame, path: Path) -> None:
    """Write multi-run tracks to CSV.

    Args:
        tracks_df: output from build_tracks.
        path: output file path.
    """
    if tracks_df.empty:
        log.info("No tracks to write")
        return
    tracks_df.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote %d tracks to %s", len(tracks_df), path)


def run_multirun_pipeline(
    file_path: str,
    run_specs: list[dict],
    years_between: list[float],
    dist_tol: float = 10.0,
    clock_tol: float = 15.0,
    cost_thresh: float = 15.0,
    output_dir: str = "outputs",
) -> pd.DataFrame:
    """Run the full multi-run tracking pipeline.

    Args:
        file_path: path to Excel file with multiple sheets.
        run_specs: list of dicts with 'sheet' and 'run_id' keys, in chronological order.
        years_between: list of year gaps between consecutive pairs.
        dist_tol, clock_tol, cost_thresh: matching parameters.
        output_dir: output directory.

    Returns:
        Tracks DataFrame.
    """
    run_ids = [s["run_id"] for s in run_specs]
    log.info("Multi-run pipeline: %s", " -> ".join(run_ids))

    pair_matches = _build_pair_matches(
        file_path, run_specs, dist_tol, clock_tol, cost_thresh,
    )

    tracks = build_tracks(pair_matches, run_ids)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_tracks_csv(tracks, out / "tracks_multi_run.csv")

    # Growth analysis for tracks with 3+ detections
    if len(run_ids) >= 3:
        depth_cols = [f"depth_{rid}" for rid in run_ids]
        available = [c for c in depth_cols if c in tracks.columns]

        if len(available) >= 3:
            times = [0.0]
            for y in years_between:
                times.append(times[-1] + y)

            analyses = []
            for _, row in tracks.iterrows():
                depths = [row.get(f"depth_{rid}") for rid in run_ids]
                if all(pd.notna(d) for d in depths):
                    result = multi_run_growth_analysis(
                        str(row["track_id"]), times, depths,
                    )
                    # Acceleration detection
                    rates = []
                    for k in range(len(depths) - 1):
                        if years_between[k] > 0:
                            rates.append((depths[k + 1] - depths[k]) / years_between[k])
                    accel = detect_acceleration(rates, years_between)
                    result["acceleration_flag"] = accel["acceleration_flag"]
                    result["rate_change_pct"] = accel["rate_change_pct"]
                    analyses.append(result)

            if analyses:
                analysis_df = pd.DataFrame(analyses)
                analysis_df.to_csv(
                    out / "multirun_growth_analysis.csv",
                    index=False, float_format="%.4f",
                )
                n_accel = analysis_df["acceleration_flag"].sum()
                log.info(
                    "Multi-run growth analysis: %d tracks analysed, %d accelerating",
                    len(analysis_df), n_accel,
                )

    return tracks
