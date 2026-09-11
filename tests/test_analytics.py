import shutil

import pandas as pd
import pytest

from src import pipeline
from src.experiment import analyze_experiment, calculate_power
from src.generate import ANALYSIS_START, EXPERIMENT_EFFECT, generate_users_and_events
from src.quality import build_quality_report
from src.retention import train_retention_model


@pytest.fixture
def generated_data():
    return generate_users_and_events(1_000, 90, seed=42)


def test_generation_is_reproducible_and_valid():
    users_a, events_a, outcomes_a = generate_users_and_events(200, 60, seed=7)
    users_b, events_b, outcomes_b = generate_users_and_events(200, 60, seed=7)
    assert users_a.equals(users_b)
    assert events_a.equals(events_b)
    assert outcomes_a.equals(outcomes_b)
    assert users_a["user_id"].is_unique
    assert events_a["event_id"].is_unique
    assert set(users_a["segment"]) <= {"individual", "team", "student"}
    assert EXPERIMENT_EFFECT == 0.025


@pytest.mark.parametrize("users,days", [(19, 60), (100, 41)])
def test_generation_rejects_unobservable_or_tiny_runs(users, days):
    with pytest.raises(ValueError):
        generate_users_and_events(users, days)


def test_generated_events_are_in_period_and_ordered(generated_data):
    users, events, _ = generated_data
    assert events["event_time"].min() >= ANALYSIS_START
    assert events["event_time"].max() < ANALYSIS_START + pd.Timedelta(days=90)
    first = events.pivot_table(
        index="user_id", columns="event_name", values="event_time", aggfunc="min"
    )
    converted = first.dropna(subset=["subscription_start"])
    assert (converted["landing_view"] <= converted["signup_start"]).all()
    assert (converted["signup_start"] <= converted["product_view"]).all()
    assert (converted["product_view"] <= converted["add_to_cart"]).all()
    assert (converted["add_to_cart"] <= converted["checkout_start"]).all()
    assert set(events["user_id"]) <= set(users["user_id"])


def test_experiment_reports_primary_guardrails_and_valid_intervals(generated_data):
    _, _, outcomes = generated_data
    result = analyze_experiment(outcomes)
    assert set(result["metric"]) == {
        "converted",
        "active_week_4",
        "support_contact_day_14",
    }
    primary = result.loc[result["metric"].eq("converted")].iloc[0]
    assert primary["control_users"] + primary["treatment_users"] == len(outcomes)
    assert primary["ci_95_low"] <= primary["absolute_lift"] <= primary["ci_95_high"]
    assert 0 <= primary["p_value"] <= 1
    assert 0 <= primary["srm_p_value"] <= 1


def test_experiment_rejects_missing_group_and_nonbinary_metric(generated_data):
    _, _, outcomes = generated_data
    with pytest.raises(ValueError, match="control and treatment"):
        analyze_experiment(outcomes[outcomes["variant"].eq("control")])
    invalid = outcomes.copy()
    invalid.loc[0, "converted"] = 2
    with pytest.raises(ValueError, match="must be binary"):
        analyze_experiment(invalid)


def test_power_analysis_is_bounded_and_mde_improves_with_sample_size():
    small = calculate_power(0.18, 0.205, 1_000, 1_000)
    large = calculate_power(0.18, 0.205, 10_000, 10_000)
    assert 0 <= small["achieved_power"] <= 1
    assert 0 <= large["achieved_power"] <= 1
    assert large["achieved_power"] > small["achieved_power"]
    assert large["mde_absolute"] < small["mde_absolute"]


def test_quality_report_passes_valid_data(generated_data):
    users, events, outcomes = generated_data
    report = build_quality_report(users, events, outcomes, days=90)
    assert len(report) == 17
    assert report["passed"].all()


def test_quality_report_detects_duplicate_event_and_bad_order(generated_data):
    users, events, outcomes = generated_data
    invalid_events = events.copy()
    invalid_events.loc[1, "event_id"] = invalid_events.loc[0, "event_id"]
    signup_index = invalid_events.index[
        invalid_events["event_name"].eq("signup_start")
    ][0]
    user_id = invalid_events.loc[signup_index, "user_id"]
    landing_time = invalid_events.loc[
        invalid_events["user_id"].eq(user_id)
        & invalid_events["event_name"].eq("landing_view"),
        "event_time",
    ].iloc[0]
    invalid_events.loc[signup_index, "event_time"] = landing_time - pd.Timedelta(minutes=1)
    report = build_quality_report(users, invalid_events, outcomes, days=90).set_index(
        "check_name"
    )
    assert not bool(report.loc["unique_event_ids", "passed"])
    assert not bool(report.loc["valid_funnel_order", "passed"])


def test_retention_model_has_strict_temporal_split_and_baseline(tmp_path, generated_data):
    users, events, outcomes = generated_data
    metrics = train_retention_model(
        users,
        events,
        outcomes,
        tmp_path / "metrics.json",
        tmp_path / "predictions.csv",
    )
    assert metrics["train_end_date"] < metrics["test_start_date"]
    assert metrics["baseline_roc_auc"] == 0.5
    assert metrics["roc_auc"] >= 0.5
    assert 0 <= metrics["f1"] <= 1
    assert sum(
        metrics[key]
        for key in ["true_negative", "false_positive", "false_negative", "true_positive"]
    ) == metrics["test_rows"]
    assert (tmp_path / "predictions.csv").exists()


def test_pipeline_writes_verified_artifacts(tmp_path, monkeypatch):
    source_sql = pipeline.ROOT / "sql" / "local_models.sql"
    (tmp_path / "sql").mkdir()
    shutil.copy(source_sql, tmp_path / "sql" / "local_models.sql")
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    summary = pipeline.run(300, 60, seed=9)
    artifacts = tmp_path / "artifacts"
    required = {
        "run_summary.json",
        "experiment_results.csv",
        "power_analysis.json",
        "retention_model_metrics.json",
        "retention_predictions.csv",
        "quality_report.csv",
        "funnel.csv",
        "funnel_by_segment.csv",
        "cohort_retention.csv",
        "channel_performance.csv",
        "experiment_summary_sql.csv",
    }
    assert required <= {path.name for path in artifacts.iterdir()}
    assert summary["quality_checks_passed"] == summary["quality_checks_total"] == 20
    funnel = pd.read_csv(artifacts / "funnel.csv")
    assert funnel["users"].is_monotonic_decreasing
    assert funnel.iloc[0]["users"] == 300
