"""Exploratory subgroup effect estimates; never used for confirmatory shipping decisions."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
from statsmodels.stats.multitest import multipletests
from experiment_validity.analysis import binary_effect


def segment_effects(
    users: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    features: tuple[str, ...] = ("channel", "device"),
    min_arm: int = 30,
) -> list[dict]:
    if users.user_id.duplicated().any() or outcomes.user_id.duplicated().any():
        raise ValueError("Segment reporting requires unique randomized user IDs")
    if not set(outcomes.user_id) == set(users.user_id):
        raise ValueError(
            "Users and outcomes must have matching ID sets; no silent drop allowed"
        )
    feature_names = [f for f in features if f in users.columns]
    if not feature_names:
        return []
    frame = outcomes[["user_id", "variant", "converted"]].merge(
        users[["user_id", *feature_names]], on="user_id", validate="one_to_one"
    )
    effects = []
    for feature in feature_names:
        for value, subset in frame.groupby(feature, dropna=False):
            sizes = subset["variant"].value_counts()
            if (
                int(sizes.get("control", 0)) < min_arm
                or int(sizes.get("treatment", 0)) < min_arm
            ):
                continue
            estimate = binary_effect(subset, "converted")
            result = asdict(estimate)
            result.update(
                {
                    "dimension": feature,
                    "segment": str(value),
                    "status": "exploratory; Holm-corrected family of reported segments",
                }
            )
            effects.append(result)
    if effects:
        adjusted = multipletests(
            [x["p_value"] for x in effects], alpha=0.05, method="holm"
        )[1]
        for item, pval in zip(effects, adjusted):
            item["holm_p_value"] = float(pval)
    return effects
