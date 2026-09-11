"""Experiment integrity checks, binary-outcome inference, and power planning."""

from __future__ import annotations

import math

import pandas as pd
from scipy.stats import chisquare
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest


def _binary_effect(outcomes: pd.DataFrame, metric: str) -> dict:
    summary = outcomes.groupby("variant")[metric].agg(["count", "sum", "mean"])
    required = {"control", "treatment"}
    if set(summary.index) != required:
        raise ValueError("Experiment requires control and treatment groups")
    if not set(outcomes[metric].dropna().unique()) <= {0, 1}:
        raise ValueError(f"{metric} must be binary")

    control_n = int(summary.loc["control", "count"])
    treatment_n = int(summary.loc["treatment", "count"])
    control_success = int(summary.loc["control", "sum"])
    treatment_success = int(summary.loc["treatment", "sum"])
    control_rate = float(summary.loc["control", "mean"])
    treatment_rate = float(summary.loc["treatment", "mean"])
    absolute_lift = treatment_rate - control_rate
    standard_error = math.sqrt(
        control_rate * (1 - control_rate) / control_n
        + treatment_rate * (1 - treatment_rate) / treatment_n
    )
    z_stat, p_value = proportions_ztest(
        [treatment_success, control_success],
        [treatment_n, control_n],
    )
    return {
        "metric": metric,
        "control_users": control_n,
        "treatment_users": treatment_n,
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "absolute_lift": absolute_lift,
        "relative_lift": absolute_lift / control_rate if control_rate else float("nan"),
        "standard_error": standard_error,
        "ci_95_low": absolute_lift - 1.96 * standard_error,
        "ci_95_high": absolute_lift + 1.96 * standard_error,
        "z_stat": float(z_stat),
        "p_value": float(p_value),
    }


def analyze_experiment(outcomes: pd.DataFrame) -> pd.DataFrame:
    """Analyze conversion plus retention and support-burden guardrails."""
    counts = outcomes.groupby("variant").size().reindex(["control", "treatment"])
    if counts.isna().any():
        raise ValueError("Experiment requires control and treatment groups")
    _, srm_p = chisquare(counts.to_numpy(), f_exp=[len(outcomes) / 2] * 2)

    rows = []
    for metric, role in [
        ("converted", "primary"),
        ("active_week_4", "guardrail"),
        ("support_contact_day_14", "guardrail"),
    ]:
        row = _binary_effect(outcomes, metric)
        row.update(
            {
                "metric_role": role,
                "srm_p_value": float(srm_p),
                "srm_flag": bool(srm_p < 0.01),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def calculate_power(
    control_rate: float,
    treatment_rate: float,
    control_users: int,
    treatment_users: int,
    alpha: float = 0.05,
    target_power: float = 0.80,
) -> dict:
    """Return achieved power and the two-sided MDE at observed sample sizes."""
    if not 0 < control_rate < 1:
        raise ValueError("control_rate must be between zero and one")
    if min(control_users, treatment_users) < 2:
        raise ValueError("Each group must contain at least two users")

    ratio = treatment_users / control_users
    analysis = NormalIndPower()
    observed_effect_size = abs(proportion_effectsize(treatment_rate, control_rate))
    achieved_power = float(
        analysis.power(
            effect_size=observed_effect_size,
            nobs1=control_users,
            alpha=alpha,
            ratio=ratio,
            alternative="two-sided",
        )
    )
    mde_effect_size = float(
        analysis.solve_power(
            effect_size=None,
            nobs1=control_users,
            alpha=alpha,
            power=target_power,
            ratio=ratio,
            alternative="two-sided",
        )
    )
    mde_rate = math.sin(math.asin(math.sqrt(control_rate)) + mde_effect_size / 2) ** 2
    return {
        "alpha": alpha,
        "target_power": target_power,
        "observed_effect_size_cohens_h": observed_effect_size,
        "achieved_power": achieved_power,
        "mde_absolute": float(mde_rate - control_rate),
        "mde_relative": float((mde_rate - control_rate) / control_rate),
        "control_users": control_users,
        "treatment_users": treatment_users,
    }
