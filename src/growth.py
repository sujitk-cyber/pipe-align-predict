"""
Corrosion growth rate calculations, severity scoring, and dig-list ranking.

Computes per-anomaly growth rates from matched pairs across two inspection
runs and ranks anomalies by a severity score combining growth rate, current
depth, and estimated remaining life.
"""

import logging
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

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
# Growth acceleration detection (for 3+ inspection runs)
# ---------------------------------------------------------------------------

def detect_acceleration(
    growth_rates: list[float],
    time_intervals: list[float],
    threshold_pct: float = 50.0,
) -> dict:
    """Detect whether corrosion growth is accelerating across consecutive run pairs.

    Compares growth rates between consecutive inspection intervals. If the
    later rate exceeds the earlier rate by more than *threshold_pct* percent,
    the anomaly is flagged as accelerating.

    Args:
        growth_rates: depth growth rates (%/yr) for each consecutive pair
                      (e.g. [rate_07_15, rate_15_22]).
        time_intervals: years between consecutive pairs (e.g. [8, 7]).
        threshold_pct: percentage increase considered significant (default 50%).

    Returns:
        Dict with acceleration_flag, rate_change_pct, and description.
    """
    result = {
        "acceleration_flag": False,
        "rate_change_pct": None,
        "rates": growth_rates,
        "description": "insufficient data",
    }

    if len(growth_rates) < 2:
        return result

    r_early = growth_rates[-2]
    r_late = growth_rates[-1]

    if r_early > 0:
        change_pct = ((r_late - r_early) / r_early) * 100.0
    elif r_late > 0:
        change_pct = float("inf")
    else:
        change_pct = 0.0

    result["rate_change_pct"] = round(change_pct, 2) if change_pct != float("inf") else None
    result["acceleration_flag"] = change_pct > threshold_pct
    if result["acceleration_flag"]:
        result["description"] = f"growth accelerating (+{change_pct:.0f}%)"
    elif change_pct < -threshold_pct:
        result["description"] = "growth decelerating"
    else:
        result["description"] = "growth stable"

    return result


def add_years_to_80pct(
    df: pd.DataFrame,
    critical_depth_pct: float = DEFAULT_CRITICAL_DEPTH_PCT,
) -> pd.DataFrame:
    """Add explicit years_to_80pct column (alias of remaining_life_yr for 80% threshold).

    If remaining_life_yr was computed with a different threshold this
    recalculates specifically for the given critical_depth_pct.

    Args:
        df: DataFrame with depth_pct_b and depth_growth_pct_per_yr.
        critical_depth_pct: threshold (default 80%).

    Returns:
        Copy of df with years_to_80pct column.
    """
    df = df.copy()
    depth_b = pd.to_numeric(df.get("depth_pct_b"), errors="coerce")
    growth = pd.to_numeric(df.get("depth_growth_pct_per_yr"), errors="coerce")

    gap = critical_depth_pct - depth_b
    yrs = np.where(
        growth > 0,
        np.where(gap > 0, gap / growth, 0.0),
        np.inf,
    )
    yrs = np.where(depth_b.notna() & growth.notna(), yrs, np.nan)
    df["years_to_80pct"] = np.round(yrs.astype(float), 2)
    return df


# ---------------------------------------------------------------------------
# Non-linear growth models (for 3+ inspection runs)
# ---------------------------------------------------------------------------

def _linear_model(t, a, b):
    """Linear: depth = a + b*t"""
    return a + b * t


def _exponential_model(t, a, b):
    """Exponential: depth = a * exp(b*t)"""
    return a * np.exp(b * t)


def _power_law_model(t, a, b):
    """Power law: depth = a * t^b  (t > 0)"""
    return a * np.power(np.maximum(t, 1e-9), b)


def _polynomial2_model(t, a, b, c):
    """Quadratic polynomial: depth = a + b*t + c*t^2"""
    return a + b * t + c * t * t


# Registry: name -> (func, n_params, initial_guess, bounds)
GROWTH_MODELS = {
    "linear": (_linear_model, 2, [1.0, 0.1], ([-np.inf, -np.inf], [np.inf, np.inf])),
    "exponential": (_exponential_model, 2, [1.0, 0.01], ([0, -1], [200, 1])),
    "power_law": (_power_law_model, 2, [1.0, 0.5], ([0, 0], [200, 5])),
    "polynomial2": (_polynomial2_model, 3, [1.0, 0.1, 0.01], ([-np.inf, -np.inf, -np.inf], [np.inf, np.inf, np.inf])),
}


def compute_aic(n: int, k: int, rss: float) -> float:
    """Akaike Information Criterion (lower is better).

    AIC = n * ln(RSS/n) + 2*k
    """
    if n <= 0 or rss <= 0:
        return np.inf
    return n * np.log(rss / n) + 2 * k


def compute_bic(n: int, k: int, rss: float) -> float:
    """Bayesian Information Criterion (lower is better).

    BIC = n * ln(RSS/n) + k * ln(n)
    """
    if n <= 0 or rss <= 0:
        return np.inf
    return n * np.log(rss / n) + k * np.log(n)


def fit_single_model(
    times: np.ndarray,
    depths: np.ndarray,
    model_name: str,
) -> dict | None:
    """Fit a single growth model to depth-vs-time data.

    Args:
        times: array of years since first run (e.g., [0, 8, 15]).
        depths: array of depth_percent at each time.
        model_name: key in GROWTH_MODELS.

    Returns:
        Dict with model_name, params, rss, aic, bic, predicted — or None if fitting fails.
    """
    if model_name not in GROWTH_MODELS:
        return None

    func, n_params, p0, bounds = GROWTH_MODELS[model_name]
    n = len(times)

    if n < n_params:
        return None

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            popt, pcov = curve_fit(func, times, depths, p0=p0, bounds=bounds, maxfev=5000)
    except (RuntimeError, ValueError, TypeError):
        return None

    predicted = func(times, *popt)
    residuals = depths - predicted
    rss = float(np.sum(residuals ** 2))

    return {
        "model_name": model_name,
        "params": popt.tolist(),
        "rss": rss,
        "aic": compute_aic(n, n_params, rss),
        "bic": compute_bic(n, n_params, rss),
        "predicted": predicted.tolist(),
    }


def select_best_model(
    times: np.ndarray,
    depths: np.ndarray,
    models: list[str] | None = None,
    criterion: str = "bic",
) -> dict | None:
    """Fit all candidate models and return the best by AIC or BIC.

    Args:
        times: years since first run.
        depths: depth_percent at each time.
        models: list of model names to try (default: all).
        criterion: "aic" or "bic" for model selection.

    Returns:
        Best fit dict (from fit_single_model) with extra key 'all_fits',
        or None if no model could be fit.
    """
    if models is None:
        models = list(GROWTH_MODELS.keys())

    fits = []
    for name in models:
        result = fit_single_model(times, depths, name)
        if result is not None:
            fits.append(result)

    if not fits:
        return None

    key = "aic" if criterion == "aic" else "bic"
    best = min(fits, key=lambda f: f[key])
    best["all_fits"] = fits
    return best


def forecast_nonlinear(
    best_fit: dict,
    forecast_years: float,
    last_time: float,
) -> float | None:
    """Project future depth using the best-fit non-linear model.

    Args:
        best_fit: output from select_best_model.
        forecast_years: years beyond last_time to project.
        last_time: years-since-first-run of the most recent inspection.

    Returns:
        Projected depth_percent, or None if model is missing.
    """
    if best_fit is None:
        return None

    model_name = best_fit["model_name"]
    func = GROWTH_MODELS[model_name][0]
    params = best_fit["params"]

    future_t = last_time + forecast_years
    try:
        return float(func(future_t, *params))
    except (ValueError, OverflowError):
        return None


def multi_run_growth_analysis(
    anomaly_id: str,
    times: list[float],
    depths: list[float],
    forecast_years: float = DEFAULT_FORECAST_YEARS,
    critical_depth_pct: float = DEFAULT_CRITICAL_DEPTH_PCT,
) -> dict:
    """Analyse growth for a single anomaly across 3+ inspection runs.

    Args:
        anomaly_id: feature identifier.
        times: years since first run for each measurement (e.g. [0, 8, 15]).
        depths: depth_percent at each time.
        forecast_years: projection horizon.
        critical_depth_pct: threshold for remaining life.

    Returns:
        Dict with best_model, projected_depth, remaining_life, all model fits.
    """
    t = np.array(times, dtype=float)
    d = np.array(depths, dtype=float)

    result = {
        "anomaly_id": anomaly_id,
        "n_runs": len(t),
        "times": times,
        "depths": depths,
    }

    if len(t) < 3:
        # Fall back to linear (2-point)
        if len(t) == 2 and t[1] > t[0]:
            rate = (d[1] - d[0]) / (t[1] - t[0])
            result["best_model"] = "linear_2pt"
            result["growth_rate_pct_per_yr"] = round(rate, 4)
            proj = d[-1] + rate * forecast_years
            result["projected_depth_pct"] = round(proj, 2)
            if rate > 0:
                result["remaining_life_yr"] = round((critical_depth_pct - d[-1]) / rate, 2) if d[-1] < critical_depth_pct else 0.0
            else:
                result["remaining_life_yr"] = np.inf
        else:
            result["best_model"] = None
        return result

    best = select_best_model(t, d)
    if best is None:
        result["best_model"] = None
        return result

    result["best_model"] = best["model_name"]
    result["params"] = best["params"]
    result["aic"] = round(best["aic"], 4)
    result["bic"] = round(best["bic"], 4)
    result["rss"] = round(best["rss"], 6)

    # Project forward
    proj = forecast_nonlinear(best, forecast_years, t[-1])
    if proj is not None:
        result["projected_depth_pct"] = round(proj, 2)

    # Estimate remaining life by finding when depth crosses critical
    # Simple bisection search over next 200 years
    func = GROWTH_MODELS[best["model_name"]][0]
    params = best["params"]
    current_depth = d[-1]

    if current_depth >= critical_depth_pct:
        result["remaining_life_yr"] = 0.0
    else:
        try:
            # Search for crossing point
            remaining = None
            for yr in np.arange(0.1, 200, 0.1):
                future_d = func(t[-1] + yr, *params)
                if future_d >= critical_depth_pct:
                    remaining = round(yr, 1)
                    break
            result["remaining_life_yr"] = remaining if remaining is not None else np.inf
        except (ValueError, OverflowError):
            result["remaining_life_yr"] = None

    # All model comparison info
    result["model_comparison"] = [
        {"model": f["model_name"], "aic": round(f["aic"], 4), "bic": round(f["bic"], 4), "rss": round(f["rss"], 6)}
        for f in best.get("all_fits", [])
    ]

    return result


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

    log.info("--- Growth analysis: computing years to 80%% WT ---")
    df = add_years_to_80pct(df, critical_depth_pct)

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
