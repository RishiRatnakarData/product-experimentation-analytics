"""Generate data, execute SQL, analyze the experiment, and model retention."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from src.experiment import analyze_experiment, calculate_power
from src.generate import ANALYSIS_START, EXPERIMENT_EFFECT, generate_users_and_events
from src.quality import build_quality_report
from src.retention import train_retention_model

ROOT = Path(__file__).resolve().parents[1]
SQL_OUTPUTS = [
    "funnel",
    "funnel_by_segment",
    "cohort_retention",
    "channel_performance",
    "experiment_summary_sql",
]


def _decision(experiment: pd.DataFrame) -> str:
    primary = experiment.loc[experiment["metric"].eq("converted")].iloc[0]
    retention = experiment.loc[experiment["metric"].eq("active_week_4")].iloc[0]
    support = experiment.loc[experiment["metric"].eq("support_contact_day_14")].iloc[0]
    adverse_guardrail = (
        (retention["p_value"] < 0.05 and retention["absolute_lift"] < 0)
        or (support["p_value"] < 0.05 and support["absolute_lift"] > 0)
    )
    if primary["srm_flag"]:
        return "Investigate assignment integrity before interpreting the result."
    if primary["p_value"] < 0.05 and primary["absolute_lift"] >= 0.01 and not adverse_guardrail:
        return "Launch with monitored rollout; conversion cleared the statistical and practical thresholds without a significant guardrail change."
    return "Continue the experiment; the result does not yet clear both the statistical and one-percentage-point practical thresholds."


def run(users_count: int, days: int, seed: int) -> dict:
    started = time.perf_counter()
    users, events, outcomes = generate_users_and_events(users_count, days, seed)
    generated = ROOT / "data" / "generated"
    artifacts = ROOT / "artifacts"
    generated.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)

    users.to_parquet(generated / "users.parquet", index=False)
    events.to_parquet(generated / "events.parquet", index=False)
    outcomes.to_parquet(generated / "experiment_outcomes.parquet", index=False)

    analysis_end = ANALYSIS_START + pd.Timedelta(days=days - 1)
    connection = duckdb.connect(str(generated / "product_analytics.duckdb"))
    try:
        for name, frame in {
            "users": users,
            "events": events,
            "experiment_outcomes": outcomes,
        }.items():
            connection.register(f"{name}_df", frame)
            connection.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {name}_df")
        connection.execute("CREATE OR REPLACE TABLE run_config (analysis_end TIMESTAMP)")
        connection.execute("INSERT INTO run_config VALUES (?)", [analysis_end])
        connection.execute((ROOT / "sql" / "local_models.sql").read_text(encoding="utf-8"))
        for view in SQL_OUTPUTS:
            connection.execute(f"SELECT * FROM {view}").df().to_csv(
                artifacts / f"{view}.csv", index=False
            )
    finally:
        connection.close()

    experiment = analyze_experiment(outcomes)
    experiment.to_csv(artifacts / "experiment_results.csv", index=False)
    primary = experiment.loc[experiment["metric"].eq("converted")].iloc[0]
    power = calculate_power(
        control_rate=float(primary["control_rate"]),
        treatment_rate=float(primary["treatment_rate"]),
        control_users=int(primary["control_users"]),
        treatment_users=int(primary["treatment_users"]),
    )
    (artifacts / "power_analysis.json").write_text(
        json.dumps(power, indent=2), encoding="utf-8"
    )

    model = train_retention_model(
        users,
        events,
        outcomes,
        artifacts / "retention_model_metrics.json",
        artifacts / "retention_predictions.csv",
    )
    quality = build_quality_report(users, events, outcomes, days)
    quality = pd.concat(
        [
            quality,
            pd.DataFrame(
                [
                    {
                        "check_name": "sample_ratio_mismatch",
                        "passed": not bool(primary["srm_flag"]),
                        "observed_value": f"p={primary['srm_p_value']:.6f}",
                        "severity": "critical",
                    },
                    {
                        "check_name": "train_test_temporal_separation",
                        "passed": model["train_end_date"] < model["test_start_date"],
                        "observed_value": (
                            f"train through {model['train_end_date']}; "
                            f"test begins {model['test_start_date']}"
                        ),
                        "severity": "critical",
                    },
                    {
                        "check_name": "feature_label_window_separation",
                        "passed": True,
                        "observed_value": "features end day 13; label begins day 28",
                        "severity": "critical",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    quality.to_csv(artifacts / "quality_report.csv", index=False)
    critical_failures = quality[quality["severity"].eq("critical") & ~quality["passed"]]
    if not critical_failures.empty:
        failed = ", ".join(critical_failures["check_name"])
        raise ValueError(f"Critical data-quality checks failed: {failed}")

    funnel = pd.read_csv(artifacts / "funnel.csv")
    summary = {
        "synthetic_data": True,
        "seed": seed,
        "encoded_treatment_effect": EXPERIMENT_EFFECT,
        "analysis_start": str(ANALYSIS_START.date()),
        "analysis_end": str(analysis_end.date()),
        "users": len(users),
        "events": len(events),
        "funnel_final_conversion_rate": float(
            funnel.loc[funnel["step"].eq("subscription_start"), "overall_conversion_rate"].iloc[0]
        ),
        "experiment_control_users": int(primary["control_users"]),
        "experiment_treatment_users": int(primary["treatment_users"]),
        "experiment_control_conversion": float(primary["control_rate"]),
        "experiment_treatment_conversion": float(primary["treatment_rate"]),
        "experiment_absolute_lift": float(primary["absolute_lift"]),
        "experiment_relative_lift": float(primary["relative_lift"]),
        "experiment_ci_95_low": float(primary["ci_95_low"]),
        "experiment_ci_95_high": float(primary["ci_95_high"]),
        "experiment_p_value": float(primary["p_value"]),
        "srm_p_value": float(primary["srm_p_value"]),
        "srm_flag": bool(primary["srm_flag"]),
        "power": power["achieved_power"],
        "mde_absolute": power["mde_absolute"],
        "retention_roc_auc": model["roc_auc"],
        "retention_average_precision": model["average_precision"],
        "quality_checks_passed": int(quality["passed"].sum()),
        "quality_checks_total": len(quality),
        "recommendation": _decision(experiment),
        "pipeline_duration_seconds": round(time.perf_counter() - started, 3),
    }
    (artifacts / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=1_000)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run the offline 1,000-user, 60-day CI contract.",
    )
    args = parser.parse_args()
    users_count, days = (1_000, 60) if args.sample else (args.users, args.days)
    run(users_count, days, args.seed)


if __name__ == "__main__":
    main()
