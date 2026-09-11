"""Leakage-aware week-four retention model with a chronological holdout."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def _feature_frame(
    users: pd.DataFrame,
    events: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> pd.DataFrame:
    event_features = events.merge(users[["user_id", "signup_date"]], on="user_id")
    event_features = event_features[
        event_features["event_time"]
        < event_features["signup_date"] + pd.Timedelta(days=14)
    ].copy()
    event_features["event_date"] = event_features["event_time"].dt.date
    event_features["is_app_open"] = event_features["event_name"].eq("app_open").astype(int)
    event_features["is_signup_start"] = (
        event_features["event_name"].eq("signup_start").astype(int)
    )
    event_features["is_conversion"] = (
        event_features["event_name"].eq("subscription_start").astype(int)
    )
    aggregates = event_features.groupby("user_id").agg(
        pre14_events=("event_id", "count"),
        pre14_active_days=("event_date", "nunique"),
        pre14_app_opens=("is_app_open", "sum"),
        signup_started=("is_signup_start", "max"),
        converted_by_day14=("is_conversion", "max"),
    )
    return (
        users.merge(aggregates, on="user_id", how="left")
        .merge(outcomes[["user_id", "active_week_4"]], on="user_id")
        .fillna(0)
        .sort_values(["signup_date", "user_id"])
    )


def train_retention_model(
    users: pd.DataFrame,
    events: pd.DataFrame,
    outcomes: pd.DataFrame,
    output: Path,
    predictions_output: Path | None = None,
) -> dict:
    """Predict activity in days 28-34 using data available before day 14."""
    frame = _feature_frame(users, events, outcomes)
    unique_dates = np.sort(frame["signup_date"].unique())
    cutoff = pd.Timestamp(unique_dates[max(1, int(len(unique_dates) * 0.8)) - 1])
    train = frame[frame["signup_date"] <= cutoff].copy()
    test = frame[frame["signup_date"] > cutoff].copy()
    if train.empty or test.empty:
        raise ValueError("Chronological split requires multiple signup dates")

    categorical = ["channel", "device", "segment", "variant"]
    numeric = [
        "pre14_events",
        "pre14_active_days",
        "pre14_app_opens",
        "signup_started",
        "converted_by_day14",
    ]
    features = categorical + numeric
    preprocessor = ColumnTransformer(
        [
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("numeric", StandardScaler(), numeric),
        ]
    )
    model = Pipeline(
        [
            ("prepare", preprocessor),
            ("model", LogisticRegression(max_iter=1_000, random_state=42)),
        ]
    )
    model.fit(train[features], train["active_week_4"])
    probability = model.predict_proba(test[features])[:, 1]
    threshold = 0.40
    prediction = (probability >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(
        test["active_week_4"], prediction, labels=[0, 1]
    ).ravel()
    prevalence = float(test["active_week_4"].mean())
    metrics = {
        "prediction_time": "end of day 13 after signup",
        "feature_window": "signup through day 13",
        "label_window": "days 28 through 34 after signup",
        "train_rows": len(train),
        "test_rows": len(test),
        "train_end_date": str(train["signup_date"].max().date()),
        "test_start_date": str(test["signup_date"].min().date()),
        "test_end_date": str(test["signup_date"].max().date()),
        "train_positive_rate": float(train["active_week_4"].mean()),
        "test_positive_rate": prevalence,
        "baseline_roc_auc": 0.5,
        "baseline_average_precision": prevalence,
        "threshold": threshold,
        "roc_auc": float(roc_auc_score(test["active_week_4"], probability)),
        "average_precision": float(
            average_precision_score(test["active_week_4"], probability)
        ),
        "precision": float(
            precision_score(test["active_week_4"], prediction, zero_division=0)
        ),
        "recall": float(recall_score(test["active_week_4"], prediction, zero_division=0)),
        "f1": float(f1_score(test["active_week_4"], prediction, zero_division=0)),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "leakage_note": "Features stop at day 13; the retention label begins on day 28.",
        "interpretation": "Predictive association only; scores do not estimate causal effects.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if predictions_output is not None:
        pd.DataFrame(
            {
                "user_id": test["user_id"].to_numpy(),
                "signup_date": test["signup_date"].to_numpy(),
                "actual_active_week_4": test["active_week_4"].to_numpy(),
                "predicted_probability": probability,
                "predicted_class": prediction,
            }
        ).to_csv(predictions_output, index=False)
    return metrics
