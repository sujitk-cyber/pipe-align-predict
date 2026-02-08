"""
Output generation: CSV files, alignment_report.json, summary printing.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def _serialise(obj):
    """JSON serialiser for numpy/pandas types."""
    # Check NaN first before any type conversion
    if pd.isna(obj):
        return None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        if np.isnan(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not serialisable: {type(obj)}")


# ---------------------------------------------------------------------------
# CSV outputs
# ---------------------------------------------------------------------------

def write_matched_csv(growth_df: pd.DataFrame, path: Path) -> None:
    """Write matched anomalies with growth data to CSV."""
    if growth_df.empty:
        log.warning("No matched anomalies to write")
        return
    growth_df.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote %d matched anomalies to %s", len(growth_df), path)


def write_missing_csv(missing_df: pd.DataFrame, path: Path) -> None:
    """Write Run A anomalies with no match (MISSING)."""
    if missing_df.empty:
        log.info("No missing anomalies to write")
        return
    missing_df.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote %d missing anomalies to %s", len(missing_df), path)


def write_new_csv(new_df: pd.DataFrame, path: Path) -> None:
    """Write Run B anomalies with no match (NEW)."""
    if new_df.empty:
        log.info("No new anomalies to write")
        return
    new_df.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote %d new anomalies to %s", len(new_df), path)


def write_summary_csv(summary_df: pd.DataFrame, path: Path) -> None:
    """Write growth summary statistics by feature type."""
    if summary_df.empty:
        log.info("No summary statistics to write")
        return
    summary_df.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote summary statistics to %s", path)


def write_dig_list_csv(growth_df: pd.DataFrame, path: Path, top_n: int = 50) -> None:
    """Write top-N most severe anomalies as a dig list.

    Columns: rank, feature_id_a, feature_id_b, feature_type, distance_a,
             depth_pct_b, depth_growth_pct_per_yr, remaining_life_yr,
             projected_depth_pct, severity_score, status
    """
    if growth_df.empty:
        log.info("No anomalies for dig list")
        return

    cols = [
        "feature_id_a", "feature_id_b", "feature_type",
        "distance_a", "clock_deg_a",
        "depth_pct_a", "depth_pct_b",
        "depth_growth_pct_per_yr", "remaining_life_yr",
        "projected_depth_pct", "severity_score", "status",
    ]
    available = [c for c in cols if c in growth_df.columns]

    # Already sorted by severity_score desc from growth module
    dig = growth_df[available].head(top_n).copy()
    dig.insert(0, "rank", range(1, len(dig) + 1))

    dig.to_csv(path, index=False, float_format="%.4f")
    log.info("Wrote top-%d dig list to %s", len(dig), path)


# ---------------------------------------------------------------------------
# JSON alignment report
# ---------------------------------------------------------------------------

def build_alignment_report(
    matched_cp: pd.DataFrame,
    residuals: pd.DataFrame,
    segments: list[dict],
    run_id_a: str,
    run_id_b: str,
    years_between: float,
    growth_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    new_df: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> dict:
    """Build a structured alignment and analysis report dict."""
    report = {
        "pipeline_run": {
            "run_a": run_id_a,
            "run_b": run_id_b,
            "years_between": years_between,
        },
        "alignment": {
            "control_points_matched": len(matched_cp),
            "segments": len(segments),
            "max_residual_ft": round(float(residuals["residual_ft"].abs().max()), 6) if not residuals.empty else None,
            "mean_residual_ft": round(float(residuals["residual_ft"].abs().mean()), 6) if not residuals.empty else None,
        },
        "matching": {
            "total_matched": len(growth_df),
            "confident": int((growth_df["status"] == "MATCHED").sum()) if not growth_df.empty and "status" in growth_df.columns else 0,
            "uncertain": int((growth_df["status"] == "UNCERTAIN").sum()) if not growth_df.empty and "status" in growth_df.columns else 0,
            "missing_run_a_only": len(missing_df),
            "new_run_b_only": len(new_df),
        },
        "growth_summary": {},
        "top_10_severity": [],
    }

    # Growth summary
    if not growth_df.empty and "depth_growth_pct_per_yr" in growth_df.columns:
        valid = growth_df["depth_growth_pct_per_yr"].dropna()
        report["growth_summary"] = {
            "anomalies_with_growth_data": int(len(valid)),
            "mean_growth_pct_per_yr": round(float(valid.mean()), 4) if len(valid) else None,
            "median_growth_pct_per_yr": round(float(valid.median()), 4) if len(valid) else None,
            "max_growth_pct_per_yr": round(float(valid.max()), 4) if len(valid) else None,
            "negative_growth_count": int(growth_df["negative_growth_flag"].sum()),
            "already_critical_count": int(growth_df["already_critical_flag"].sum()),
        }

    # Summary by feature type
    if not summary_df.empty:
        # Convert NaN to None for valid JSON
        records = summary_df.to_dict(orient="records")
        for rec in records:
            for k, v in rec.items():
                if isinstance(v, float) and (pd.isna(v) or np.isnan(v)):
                    rec[k] = None
        report["growth_by_feature_type"] = records

    # Top 10 most severe
    if not growth_df.empty and "severity_score" in growth_df.columns:
        top = growth_df.head(10)
        top_cols = [
            "feature_id_a", "feature_type", "distance_a",
            "depth_pct_a", "depth_pct_b",
            "depth_growth_pct_per_yr", "remaining_life_yr",
            "severity_score",
        ]
        available = [c for c in top_cols if c in top.columns]
        for _, row in top[available].iterrows():
            entry = {}
            for col in available:
                val = row[col]
                if pd.isna(val):
                    entry[col] = None
                elif isinstance(val, float):
                    entry[col] = round(val, 4)
                else:
                    entry[col] = val
            report["top_10_severity"].append(entry)

    return report


def write_alignment_report(report: dict, path: Path) -> None:
    """Write alignment report as JSON."""
    # First dump to string, then replace NaN/Infinity with null
    import re
    json_str = json.dumps(report, indent=2, default=_serialise)
    # Replace NaN and Infinity with null (case-sensitive, word boundary)
    json_str = re.sub(r'\bNaN\b', 'null', json_str)
    json_str = re.sub(r'\bInfinity\b', 'null', json_str)
    json_str = re.sub(r'\b-Infinity\b', 'null', json_str)
    with open(path, "w") as f:
        f.write(json_str)
    log.info("Wrote alignment report to %s", path)


# ---------------------------------------------------------------------------
# High-level output orchestrator
# ---------------------------------------------------------------------------

def write_all_outputs(
    growth_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    new_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    matched_cp: pd.DataFrame,
    residuals: pd.DataFrame,
    segments: list[dict],
    run_id_a: str,
    run_id_b: str,
    years_between: float,
    output_dir: Path,
    html_report: bool = False,
) -> None:
    """Write all pipeline output files to output_dir.

    Files created:
        matched_results.csv      – matched pairs with growth data
        missing_anomalies.csv    – Run A anomalies with no match
        new_anomalies.csv        – Run B anomalies with no match
        growth_summary.csv       – stats by feature type
        dig_list.csv             – top-50 most severe anomalies
        alignment_report.json    – full structured report
        report.html              – interactive HTML report (if html_report=True)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_matched_csv(growth_df, output_dir / "matched_results.csv")
    write_missing_csv(missing_df, output_dir / "missing_anomalies.csv")
    write_new_csv(new_df, output_dir / "new_anomalies.csv")
    write_summary_csv(summary_df, output_dir / "growth_summary.csv")
    write_dig_list_csv(growth_df, output_dir / "dig_list.csv")

    report = build_alignment_report(
        matched_cp=matched_cp,
        residuals=residuals,
        segments=segments,
        run_id_a=run_id_a,
        run_id_b=run_id_b,
        years_between=years_between,
        growth_df=growth_df,
        missing_df=missing_df,
        new_df=new_df,
        summary_df=summary_df,
    )
    write_alignment_report(report, output_dir / "alignment_report.json")

    if html_report:
        try:
            from .html_report import generate_html_report
            generate_html_report(
                growth_df=growth_df,
                missing_df=missing_df,
                new_df=new_df,
                summary_df=summary_df,
                segments=segments,
                residuals=residuals,
                run_id_a=run_id_a,
                run_id_b=run_id_b,
                years_between=years_between,
                output_path=output_dir / "report.html",
            )
        except ImportError:
            log.warning("plotly/jinja2 not installed — skipping HTML report")

    log.info("All outputs written to %s/", output_dir)
