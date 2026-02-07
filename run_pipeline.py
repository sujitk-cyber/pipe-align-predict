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
    )

    # --- Growth ---
    log.info("Running growth analysis (%.1f year gap)...", args.years)
    growth_df, summary_df = run_growth_analysis(
        matched_df,
        years_between=args.years,
        critical_depth_pct=args.critical_depth,
        forecast_years=args.forecast_years,
    )

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
    )

    # --- Final summary ---
    n_matched = len(growth_df)
    n_missing = len(missing_df)
    n_new = len(new_df)
    print(f"\nPipeline complete:")
    print(f"  Matched anomalies:  {n_matched}")
    print(f"  Missing (Run A only): {n_missing}")
    print(f"  New (Run B only):     {n_new}")
    if not growth_df.empty and "depth_growth_pct_per_yr" in growth_df.columns:
        valid = growth_df["depth_growth_pct_per_yr"].dropna()
        if len(valid):
            print(f"  Mean growth rate:   {valid.mean():.3f} %WT/yr")
            print(f"  Max growth rate:    {valid.max():.3f} %WT/yr")
    print(f"  Outputs written to: {output_dir}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
