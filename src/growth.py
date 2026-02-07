"""
Corrosion growth rate calculations, severity scoring, and dig-list ranking.

Computes per-anomaly growth rates from matched pairs across two inspection
runs and ranks anomalies by a severity score combining growth rate, current
depth, and estimated remaining life.
"""

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CRITICAL_DEPTH_PCT = 80.0   # % wall loss — typical dig threshold
DEFAULT_FORECAST_YEARS = 5


# ---------------------------------------------------------------------------
# Growth rate calculation
# ---------------------------------------------------------------------------

def compute_growth_rates(
    matched_df: pd.DataFrame,
    years_between: float,
) -> pd.DataFrame:
    """Add growth-rate columns to matched anomaly pairs.

    New columns added:
        depth_growth_pct_per_yr   – (depth_B − depth_A) / years
        length_growth_in_per_yr   – (length_B − length_A) / years
        width_growth_in_per_yr    – (width_B − width_A) / years
        negative_growth_flag      – True if depth growth < 0
                                    (possible measurement error)

    Args:
        matched_df: output from matching.match_anomalies (matched pairs).
        years_between: time gap between Run A and Run B in years.

    Returns:
        A copy of matched_df with the additional columns.
    """
    if matched_df.empty:
        log.warning("No matched anomalies — skipping growth calculation")
        return matched_df.copy()

    if years_between <= 0:
        raise ValueError(f"years_between must be positive, got {years_between}")

    df = matched_df.copy()

    # Depth growth (%WT / yr)
    depth_a = pd.to_numeric(df.get("depth_pct_a"), errors="coerce")
    depth_b = pd.to_numeric(df.get("depth_pct_b"), errors="coerce")
    df["depth_growth_pct_per_yr"] = np.where(
        depth_a.notna() & depth_b.notna(),
        (depth_b - depth_a) / years_between,
        np.nan,
    )

    # Length growth (in / yr)
    len_a = pd.to_numeric(df.get("length_a"), errors="coerce")
    len_b = pd.to_numeric(df.get("length_b"), errors="coerce")
    df["length_growth_in_per_yr"] = np.where(
        len_a.notna() & len_b.notna(),
        (len_b - len_a) / years_between,
        np.nan,
    )

    # Width growth (in / yr)
    wid_a = pd.to_numeric(df.get("width_a"), errors="coerce")
    wid_b = pd.to_numeric(df.get("width_b"), errors="coerce")
    df["width_growth_in_per_yr"] = np.where(
        wid_a.notna() & wid_b.notna(),
        (wid_b - wid_a) / years_between,
        np.nan,
    )

    # Flag negative depth growth (possible measurement artefact)
    df["negative_growth_flag"] = df["depth_growth_pct_per_yr"] < 0

    n_neg = df["negative_growth_flag"].sum()
    n_valid = df["depth_growth_pct_per_yr"].notna().sum()
    log.info(
        "Growth rates computed: %d valid depth rates, %d negative-growth flagged",
        n_valid, n_neg,
    )

    return df


# ---------------------------------------------------------------------------
# Remaining life estimation
# ---------------------------------------------------------------------------

def estimate_remaining_life(
    df: pd.DataFrame,
    critical_depth_pct: float = DEFAULT_CRITICAL_DEPTH_PCT,
) -> pd.DataFrame:
    """Estimate years to critical depth for each anomaly.

    remaining_life_yr = (critical_depth − depth_B) / growth_rate

    Rules:
        - growth_rate <= 0  →  inf  (not growing / measurement error)
        - depth_B >= critical →  0   (already critical)
        - missing data       →  NaN

    Adds columns:
        remaining_life_yr     – estimated years until critical_depth_pct
        already_critical_flag – True if current depth >= critical threshold

    Args:
        df: DataFrame with depth_pct_b and depth_growth_pct_per_yr columns.
        critical_depth_pct: wall-loss % at which repair is needed.

    Returns:
        Copy of df with new columns.
    """
    df = df.copy()
    depth_b = pd.to_numeric(df.get("depth_pct_b"), errors="coerce")
    growth = pd.to_numeric(df.get("depth_growth_pct_per_yr"), errors="coerce")

    remaining = pd.Series(np.nan, index=df.index)

    # Positive growth — compute time to reach critical
    pos_mask = growth > 0
    gap = critical_depth_pct - depth_b
    remaining = np.where(
        pos_mask & depth_b.notna(),
        np.where(gap > 0, gap / growth, 0.0),
        remaining,
    )

    # Non-positive growth → infinite remaining life
    remaining = np.where(
        growth.notna() & (growth <= 0) & depth_b.notna(),
        np.inf,
        remaining,
    )

    df["remaining_life_yr"] = np.round(remaining.astype(float), 2)
    df["already_critical_flag"] = depth_b >= critical_depth_pct

    n_critical = df["already_critical_flag"].sum()
    log.info(
        "Remaining life estimated: %d anomalies already at or above %.0f%% WT",
        n_critical, critical_depth_pct,
    )

    return df


# ---------------------------------------------------------------------------
# Severity scoring and dig-list ranking
# ---------------------------------------------------------------------------

def compute_severity_score(
    df: pd.DataFrame,
    w_growth: float = 0.4,
    w_depth: float = 0.35,
    w_remaining: float = 0.25,
) -> pd.DataFrame:
    """Compute a 0-100 severity score for dig-list prioritisation.

    Score = w_growth * norm(growth_rate)
          + w_depth  * norm(depth_B)
          + w_remaining * norm(1 / remaining_life)

    Each component is min-max normalised to [0, 1] before weighting,
    then the total is scaled to 0-100.

    Adds column:
        severity_score – float 0-100, higher = more severe

    Args:
        df: DataFrame with depth_pct_b, depth_growth_pct_per_yr,
            remaining_life_yr columns.
        w_growth, w_depth, w_remaining: weights summing to 1.0.

    Returns:
        Copy of df with severity_score column, sorted by score descending.
    """
    df = df.copy()

    def _minmax(series: pd.Series) -> pd.Series:
        s = series.fillna(0)
        lo, hi = s.min(), s.max()
        if hi - lo < 1e-12:
            return pd.Series(0.0, index=series.index)
        return (s - lo) / (hi - lo)

    growth = pd.to_numeric(df.get("depth_growth_pct_per_yr"), errors="coerce").clip(lower=0)
    depth = pd.to_numeric(df.get("depth_pct_b"), errors="coerce").fillna(0)
    remaining = pd.to_numeric(df.get("remaining_life_yr"), errors="coerce")

    # Invert remaining life: shorter remaining → higher urgency
    # Replace inf with a large number so it normalises near 0
    inv_remaining = 1.0 / remaining.replace(0, np.nan).fillna(np.inf)
    inv_remaining = inv_remaining.replace([np.inf, -np.inf], 0)

    score = (
        w_growth * _minmax(growth)
        + w_depth * _minmax(depth)
        + w_remaining * _minmax(inv_remaining)
    ) * 100.0

    df["severity_score"] = np.round(score, 2)
    df = df.sort_values("severity_score", ascending=False).reset_index(drop=True)

    log.info(
        "Severity scores: max=%.1f, median=%.1f, min=%.1f",
        df["severity_score"].max(),
        df["severity_score"].median(),
        df["severity_score"].min(),
    )

    return df


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def growth_summary_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute growth-rate summary statistics grouped by feature type.

    Returns DataFrame with columns:
        feature_type, count, mean_growth, median_growth, max_growth,
        std_growth, pct_negative
    """
    if df.empty or "depth_growth_pct_per_yr" not in df.columns:
        return pd.DataFrame()

    growth_col = "depth_growth_pct_per_yr"
    grouped = df.groupby("feature_type")[growth_col]

    stats = pd.DataFrame({
        "count": grouped.count(),
        "mean_growth": grouped.mean(),
        "median_growth": grouped.median(),
        "max_growth": grouped.max(),
        "std_growth": grouped.std(),
        "pct_negative": grouped.apply(lambda s: (s < 0).mean() * 100),
    }).reset_index()

    # Round for readability
    for col in ["mean_growth", "median_growth", "max_growth", "std_growth", "pct_negative"]:
        stats[col] = stats[col].round(4)

    return stats


# ---------------------------------------------------------------------------
# Forecasting (simple linear extrapolation)
# ---------------------------------------------------------------------------

def forecast_depth(
    df: pd.DataFrame,
    forecast_years: float = DEFAULT_FORECAST_YEARS,
) -> pd.DataFrame:
    """Project future depth using linear extrapolation.

    projected_depth = depth_B + growth_rate * forecast_years

    Adds columns:
        projected_depth_pct  – projected %WT at forecast horizon
        forecast_years       – the horizon used

    Args:
        df: DataFrame with depth_pct_b and depth_growth_pct_per_yr.
        forecast_years: years into the future to project.

    Returns:
        Copy of df with new columns.
    """
    df = df.copy()
    depth_b = pd.to_numeric(df.get("depth_pct_b"), errors="coerce")
    growth = pd.to_numeric(df.get("depth_growth_pct_per_yr"), errors="coerce")

    # Only project for positive growth — negative growth anomalies
    # keep their current depth as projection
    projected = np.where(
        growth > 0,
        depth_b + growth * forecast_years,
        depth_b,
    )

    df["projected_depth_pct"] = np.round(
        np.where(depth_b.notna() & growth.notna(), projected, np.nan), 2
    )
    df["forecast_years"] = forecast_years

    n_above_80 = (df["projected_depth_pct"] >= 80).sum()
    log.info(
        "Forecast (%d yr): %d anomalies projected to reach >= 80%% WT",
        forecast_years, n_above_80,
    )

    return df


# ---------------------------------------------------------------------------
# High-level growth pipeline
# ---------------------------------------------------------------------------

def run_growth_analysis(
    matched_df: pd.DataFrame,
    years_between: float,
    critical_depth_pct: float = DEFAULT_CRITICAL_DEPTH_PCT,
    forecast_years: float = DEFAULT_FORECAST_YEARS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Full growth analysis pipeline.

    1. Compute growth rates
    2. Estimate remaining life
    3. Forecast future depth
    4. Compute severity scores
    5. Generate summary stats

    Args:
        matched_df: matched anomaly pairs from matching module.
        years_between: years between Run A and Run B.
        critical_depth_pct: wall-loss threshold for remaining life calc.
        forecast_years: projection horizon in years.

    Returns:
        (growth_df, summary_df)
        - growth_df: matched_df augmented with all growth columns, sorted by severity.
        - summary_df: summary statistics by feature type.
    """
    log.info("--- Growth analysis: computing rates (%.1f yr gap) ---", years_between)
    df = compute_growth_rates(matched_df, years_between)

    log.info("--- Growth analysis: estimating remaining life (critical=%.0f%%) ---", critical_depth_pct)
    df = estimate_remaining_life(df, critical_depth_pct)

    log.info("--- Growth analysis: forecasting %d years ---", forecast_years)
    df = forecast_depth(df, forecast_years)

    log.info("--- Growth analysis: scoring severity ---")
    df = compute_severity_score(df)

    summary = growth_summary_stats(df)

    # Top-level summary
    if not df.empty and "depth_growth_pct_per_yr" in df.columns:
        valid = df["depth_growth_pct_per_yr"].dropna()
        log.info(
            "Growth analysis complete: %d anomalies, "
            "mean growth=%.3f %%/yr, max=%.3f %%/yr, "
            "%d flagged negative, %d already critical",
            len(df),
            valid.mean() if len(valid) else 0,
            valid.max() if len(valid) else 0,
            df["negative_growth_flag"].sum(),
            df["already_critical_flag"].sum(),
        )

    return df, summary
