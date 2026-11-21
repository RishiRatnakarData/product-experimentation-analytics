"""User-level CUPED variance reduction for randomized, synthetic experiments.

The covariate must be measured before assignment/exposure. Naming rules help
prevent mistakes but cannot establish measurement chronology by themselves.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import t


def _validate(
    frame: pd.DataFrame, *, outcome: str, covariate: str,
    arm: str, user: str,
) -> pd.DataFrame:
    required = {outcome, covariate, arm, user}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if not covariate.startswith("pre_") or covariate in {outcome, arm, user}:
        raise ValueError(
            "Covariate must be a documented pre-treatment measure with 'pre_' prefix"
        )
    if frame.empty or frame[user].isna().any() or frame[user].duplicated().any():
        raise ValueError("Expected one unique, nonmissing row per assigned user")
    if frame[arm].isna().any() or set(frame[arm].unique()) != {"control", "treatment"}:
        raise ValueError("Need exactly control and treatment assignment groups")

    copy = frame.copy()
    response = pd.to_numeric(copy[outcome], errors="coerce")
    if response.isna().any() or not response.isin([0, 1]).all():
        raise ValueError("Outcome must be 0 or 1 for every randomized user")
    copy[outcome] = response.astype(float)
    numeric = pd.to_numeric(copy[covariate], errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Pre-treatment covariate must be complete and finite")
    copy[covariate] = numeric.astype(float)
    group_sizes = copy[arm].value_counts()
    if group_sizes.min() < 10:
        raise ValueError("Need at least 10 users per assignment arm")
    if any(copy.loc[copy[arm] == group, covariate].nunique() < 2 for group in ("control", "treatment")):
        raise ValueError("Pre-treatment covariate must vary in both arms")
    return copy


def _comparison(y0: np.ndarray, y1: np.ndarray, *, alpha: float) -> dict:
    """Welch approximate CI and p-value for treatment-minus-control mean."""
    n0, n1 = len(y0), len(y1)
    m0, m1 = float(np.mean(y0)), float(np.mean(y1))
    v0, v1 = float(np.var(y0, ddof=1)), float(np.var(y1, ddof=1))
    effect = m1 - m0
    a, b = v0 / n0, v1 / n1
    se = math.sqrt(a + b)
    if se > 0:
        df = (a + b) ** 2 / (a * a / (n0 - 1) + b * b / (n1 - 1))
        critical = float(t.ppf(1 - alpha / 2, df))
        p_value = float(2 * t.sf(abs(effect / se), df))
        low, high = effect - critical * se, effect + critical * se
    else:
        df, p_value, low, high = None, None, None, None
    return {
        "control_mean": m0,
        "treatment_mean": m1,
        "effect": effect,
        "standard_error": se,
        "confidence_level": 1 - alpha,
        "ci_low": low,
        "ci_high": high,
        "p_value": p_value,
        "welch_degrees_of_freedom": df,
        "control_n": n0,
        "treatment_n": n1,
    }


def analyze_cuped(
    frame: pd.DataFrame, *,
    covariate: str = "pre_period_engagement_score",
    outcome: str = "converted",
    arm: str = "variant",
    user: str = "user_id",
    alpha: float = 0.05,
) -> dict[str, object]:
    """Estimate variance-reduced treatment effect with a pre-treatment covariate.

    CUPED slope theta uses *within-arm centered* covariances, so treatment
    mean differences are not used to fit the nuisance adjustment coefficient.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    df = _validate(frame, outcome=outcome, covariate=covariate, arm=arm, user=user)
    control = df[arm].eq("control").to_numpy()
    treatment = ~control
    x = df[covariate].to_numpy(dtype=float)
    y = df[outcome].to_numpy(dtype=float)
    x0, x1 = x[control], x[treatment]
    y0, y1 = y[control], y[treatment]
    cx0, cx1 = x0 - x0.mean(), x1 - x1.mean()
    cy0, cy1 = y0 - y0.mean(), y1 - y1.mean()
    denominator = float(np.dot(cx0, cx0) + np.dot(cx1, cx1))
    if denominator <= 0:
        raise ValueError("Pre-treatment covariate has no within-arm variance")
    theta = float((np.dot(cx0, cy0) + np.dot(cx1, cy1)) / denominator)
    adjusted = y - theta * (x - x.mean())
    original = _comparison(y0, y1, alpha=alpha)
    cuped = _comparison(adjusted[control], adjusted[treatment], alpha=alpha)
    baseline_var = float((np.dot(cy0, cy0) + np.dot(cy1, cy1)) / (len(df) - 2))
    adjusted_var = float(
        (np.var(adjusted[control], ddof=1) * (len(y0) - 1)
         + np.var(adjusted[treatment], ddof=1) * (len(y1) - 1)) / (len(df) - 2)
    )
    reduction = 1 - adjusted_var / baseline_var if baseline_var > 0 else None
    # The coefficient is estimated in this data. Approximate Welch SEs do not
    # explicitly account for theta estimation uncertainty (small-sample caveat).
    interpretation = (
        "CUPED reduced observed within-arm variance in this synthetic experiment."
        if reduction is not None and reduction > 0
        else "CUPED did not reduce observed within-arm variance in this sample."
    )
    return {
        "analysis_type": "synthetic_user_level_cuped_demonstration",
        "estimand": "treatment_minus_control_conversion_rate",
        "covariate": covariate,
        "covariate_timing": "must_be_pre_randomization_or_pre_exposure; verify_from_source_metadata",
        "theta_within_arm": theta,
        "covariate_mean": float(x.mean()),
        "original": original,
        "cuped_adjusted": cuped,
        "pooled_within_arm_variance_original": baseline_var,
        "pooled_within_arm_variance_adjusted": adjusted_var,
        "measured_variance_reduction_fraction": reduction,
        "interpretation": interpretation,
        "caveats": [
            "Synthetic outcomes; no observed commercial experiment or real business lift.",
            "Covariate provenance must independently establish pre-treatment timing; a column name alone cannot prove it.",
            "Coefficient is estimated within arms; reported Welch standard errors are approximate and omit theta estimation uncertainty.",
            "No significance or power gain is guaranteed. Report realized estimates and uncertainty.",
            "CUPED-adjusted individual values are not probabilities and may fall outside [0, 1].",
            "Sample-ratio mismatch should be investigated with the existing SRM audit before making an experiment decision.",
        ],
    }
