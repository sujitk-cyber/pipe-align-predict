#!/usr/bin/env python3
"""
CLI entry point for the ILI alignment and growth analysis pipeline.

Usage:
    python run_pipeline.py ILIDataV2.xlsx --sheet_a 2007 --sheet_b 2015 --years 8
    python run_pipeline.py run1.csv run2.csv --years 10 --output_dir results/
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from src.io import load_run
from src.alignment import align_runs
from src.matching import match_anomalies, DEFAULT_DIST_TOL, DEFAULT_CLOCK_TOL, DEFAULT_COST_THRESH
from src.growth import run_growth_analysis, DEFAULT_CRITICAL_DEPTH_PCT, DEFAULT_FORECAST_YEARS
from src.reporting import write_all_outputs


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="ILI Pipeline Alignment & Corrosion Growth Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Two sheets from one Excel file
  python run_pipeline.py ILIDataV2.xlsx --sheet_a 2007 --sheet_b 2015 --years 8

  # Two separate CSV files
  python run_pipeline.py run1.csv run2.csv --years 10

  # Full options
  python run_pipeline.py data.xlsx --sheet_a 2015 --sheet_b 2022 --years 7 \\
      --dist_tol 15 --clock_tol 20 --cost_thresh 20 \\
      --critical_depth 80 --forecast_years 5 --output_dir results/
""",
    )

    # Input files
    p.add_argument(
        "file_a",
        help="Path to Run A data file (Excel or CSV). "
             "If only one file is given, use --sheet_a and --sheet_b for different sheets.",
    )
    p.add_argument(
        "file_b",
        nargs="?",
        default=None,
        help="Path to Run B data file (optional if using sheets from file_a).",
    )

    # Sheet selection
    p.add_argument("--sheet_a", default="0", help="Sheet name/index for Run A (default: first sheet).")
    p.add_argument("--sheet_b", default="1", help="Sheet name/index for Run B (default: second sheet).")

    # Run IDs
    p.add_argument("--run_id_a", default=None, help="Run ID for Run A (default: derived from filename/sheet).")
    p.add_argument("--run_id_b", default=None, help="Run ID for Run B (default: derived from filename/sheet).")

    # Years between runs
    p.add_argument(
        "--years", type=float, required=True,
        help="Years between Run A and Run B (required for growth calculations).",
    )

    # Matching parameters
    p.add_argument("--dist_tol", type=float, default=DEFAULT_DIST_TOL,
                   help=f"Distance tolerance in feet (default: {DEFAULT_DIST_TOL}).")
    p.add_argument("--clock_tol", type=float, default=DEFAULT_CLOCK_TOL,
                   help=f"Clock tolerance in degrees (default: {DEFAULT_CLOCK_TOL}).")
    p.add_argument("--cost_thresh", type=float, default=DEFAULT_COST_THRESH,
                   help=f"Cost threshold for UNCERTAIN flag (default: {DEFAULT_COST_THRESH}).")

    # Growth parameters
    p.add_argument("--critical_depth", type=float, default=DEFAULT_CRITICAL_DEPTH_PCT,
                   help=f"Critical depth %% WT for remaining life (default: {DEFAULT_CRITICAL_DEPTH_PCT}).")
    p.add_argument("--forecast_years", type=float, default=DEFAULT_FORECAST_YEARS,
                   help=f"Forecast horizon in years (default: {DEFAULT_FORECAST_YEARS}).")

    # Output
    p.add_argument("--output_dir", "-o", default="outputs",
                   help="Output directory (default: outputs/).")
    p.add_argument("--html_report", action="store_true",
                   help="Generate an interactive HTML report (requires plotly & jinja2).")

    # Confidence scoring
    p.add_argument("--enable_confidence", action="store_true",
                   help="Add probabilistic and confidence scoring columns to matched output.")

    # Clustering
    p.add_argument("--clustering_epsilon", type=float, default=None,
                   help="DBSCAN epsilon (ft) for anomaly clustering. Omit to skip clustering.")
    p.add_argument("--clustering_mode", choices=["1d", "2d"], default="1d",
                   help="Clustering mode: 1d (distance only) or 2d (distance + clock). Default: 1d.")

    # Multi-run
    p.add_argument("--enable_multirun", action="store_true",
                   help="Enable multi-run tracking across 3+ runs.")
    p.add_argument("--runs", default=None,
                   help="Comma-separated sheet names for multi-run (e.g. 2007,2015,2022).")
    p.add_argument("--run_years", default=None,
                   help="Comma-separated year gaps between consecutive runs (e.g. 8,7).")

    # Verbosity
    p.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging.")
    p.add_argument("--quiet", "-q", action="store_true", help="Suppress info logging.")

    return p.parse_args(argv)


def _parse_sheet(val: str):
    """Convert sheet arg to int only for small indices (0-9), else keep as string name."""
    try:
        n = int(val)
        # Only treat as index if it looks like a small sheet index, not a year
        if 0 <= n <= 9:
            return n
        return val  # keep "2015", "2022" etc. as string sheet names
    except ValueError:
        return val


def main(argv=None):
    args = parse_args(argv)

    # Logging setup
    level = logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("pipeline")

    # Resolve input files
    file_a = args.file_a
    file_b = args.file_b if args.file_b else args.file_a
    sheet_a = _parse_sheet(args.sheet_a)
    sheet_b = _parse_sheet(args.sheet_b)

    # Derive run IDs
    run_id_a = args.run_id_a or f"run_{sheet_a}"
    run_id_b = args.run_id_b or f"run_{sheet_b}"

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Multi-run mode ---
    if args.enable_multirun and args.runs:
        from src.multirun import run_multirun_pipeline
        sheets = [_parse_sheet(s.strip()) for s in args.runs.split(",")]
        run_specs = [{"sheet": s, "run_id": str(s)} for s in sheets]

        if args.run_years:
            years_list = [float(y.strip()) for y in args.run_years.split(",")]
        else:
            years_list = [args.years] * (len(sheets) - 1)

        log.info("Multi-run mode: %s", " -> ".join(str(s) for s in sheets))
        tracks = run_multirun_pipeline(
            file_path=file_a,
            run_specs=run_specs,
            years_between=years_list,
            dist_tol=args.dist_tol,
            clock_tol=args.clock_tol,
            cost_thresh=args.cost_thresh,
            output_dir=str(output_dir),
        )
        print(f"\nMulti-run pipeline complete: {len(tracks)} tracks across {len(sheets)} runs")
        print(f"  Outputs written to: {output_dir}/")
        return 0

    # --- Load ---
    log.info("Loading Run A: %s (sheet=%s)", file_a, sheet_a)
    df_a, info_a = load_run(file_a, run_id_a, sheet_name=sheet_a)
    log.info("Loading Run B: %s (sheet=%s)", file_b, sheet_b)
    df_b, info_b = load_run(file_b, run_id_b, sheet_name=sheet_b)

    # --- Align ---
    log.info("Aligning runs...")
    df_b_aligned, segments, matched_cp, residuals = align_runs(df_a, df_b)

    # --- Match ---
    log.info("Matching anomalies...")
    matched_df, missing_df, new_df = match_anomalies(
        df_a, df_b_aligned, matched_cp,
        dist_tol=args.dist_tol,
        clock_tol=args.clock_tol,
        cost_thresh=args.cost_thresh,
        enable_confidence=args.enable_confidence,
    )

    # --- Growth ---
    log.info("Running growth analysis (%.1f year gap)...", args.years)
    growth_df, summary_df = run_growth_analysis(
        matched_df,
        years_between=args.years,
        critical_depth_pct=args.critical_depth,
        forecast_years=args.forecast_years,
    )

    # --- Clustering (optional) ---
    if args.clustering_epsilon is not None:
        from src.clustering import cluster_anomalies, compute_cluster_metrics, write_clusters_summary
        log.info("Clustering anomalies (eps=%.1f, mode=%s)...", args.clustering_epsilon, args.clustering_mode)
        growth_df = cluster_anomalies(growth_df, epsilon=args.clustering_epsilon, mode=args.clustering_mode)
        cluster_metrics = compute_cluster_metrics(growth_df)
        write_clusters_summary(cluster_metrics, output_dir / "clusters_summary.csv")

    # --- Output ---
    log.info("Writing outputs to %s/", output_dir)
    write_all_outputs(
        growth_df=growth_df,
        missing_df=missing_df,
        new_df=new_df,
        summary_df=summary_df,
        matched_cp=matched_cp,
        residuals=residuals,
        segments=segments,
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        years_between=args.years,
        output_dir=output_dir,
        html_report=args.html_report,
    )

    # --- Final summary ---
    n_a = len(df_a)
    n_b = len(df_b)
    n_matched = len(growth_df)
    n_missing = len(missing_df)
    n_new = len(new_df)
    n_uncertain = int((growth_df["status"] == "UNCERTAIN").sum()) if not growth_df.empty and "status" in growth_df.columns else 0

    print(f"\n{'='*60}")
    print(f"  Pipeline Complete — {run_id_a} vs {run_id_b}")
    print(f"{'='*60}")
    print(f"  Run A features:       {n_a}")
    print(f"  Run B features:       {n_b}")
    print(f"  Matched anomalies:    {n_matched}  ({n_matched - n_uncertain} confident, {n_uncertain} uncertain)")
    print(f"  Missing (Run A only): {n_missing}")
    print(f"  New (Run B only):     {n_new}")

    if not growth_df.empty and "depth_growth_pct_per_yr" in growth_df.columns:
        valid = growth_df["depth_growth_pct_per_yr"].dropna()
        if len(valid):
            neg = (valid < 0).sum()
            print(f"\n  Growth statistics ({args.years:.0f}-year gap):")
            print(f"    Mean growth rate:   {valid.mean():.3f} %WT/yr")
            print(f"    Median growth rate: {valid.median():.3f} %WT/yr")
            print(f"    Max growth rate:    {valid.max():.3f} %WT/yr")
            print(f"    Negative growth:    {neg} (possible measurement error)")

        # Top-10 fastest-growing anomalies
        if "severity_score" in growth_df.columns:
            top = growth_df.head(10)
            cols_show = ["feature_id_a", "feature_type", "distance_a",
                         "depth_pct_b", "depth_growth_pct_per_yr",
                         "remaining_life_yr", "severity_score"]
            available = [c for c in cols_show if c in top.columns]
            if available:
                print(f"\n  Top-10 most severe anomalies:")
                print(f"  {'Rank':<5} {'Feature ID':<12} {'Type':<16} {'Dist(ft)':<10} "
                      f"{'Depth%':<8} {'Growth/yr':<10} {'Life(yr)':<10} {'Score':<6}")
                print(f"  {'-'*77}")
                for rank, (_, row) in enumerate(top.iterrows(), 1):
                    fid = row.get("feature_id_a", "?")
                    ftype = str(row.get("feature_type", "?"))[:15]
                    dist = row.get("distance_a", float("nan"))
                    depth = row.get("depth_pct_b", float("nan"))
                    gr = row.get("depth_growth_pct_per_yr", float("nan"))
                    life = row.get("remaining_life_yr", float("nan"))
                    sev = row.get("severity_score", float("nan"))
                    life_s = f"{life:.1f}" if life != float("inf") and pd.notna(life) else "inf"
                    print(f"  {rank:<5} {str(fid):<12} {ftype:<16} {dist:<10.1f} "
                          f"{depth:<8.1f} {gr:<10.3f} {life_s:<10} {sev:<6.1f}")

    print(f"\n  Outputs written to: {output_dir}/")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
