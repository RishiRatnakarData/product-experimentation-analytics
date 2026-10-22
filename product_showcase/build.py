"""Build a recruiter-facing project showcase exclusively from verified local artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from experiment_validity.analysis import analyze
from experiment_validity.report import save_effect_plot, write_outputs
from .visuals import channel_chart, conversion_chart, retention_chart, subgroup_chart
from .segments import segment_effects

GALLERY_KEYWORDS = {
    "Executive overview": ("executive", "overview"),
    "Conversion funnel": ("funnel",),
    "Cohort retention": ("cohort", "retention"),
    "Model and data quality": ("model", "quality"),
}


def find_dashboard_images(repo: Path) -> list[tuple[str, str]]:
    paths = []
    for p in (repo / "docs").rglob("*"):
        if (
            p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
            and "evidence" not in p.parts
            and "showcase" not in p.parts
            and not p.stem.lower().startswith("showcase_")
        ):
            paths.append(p)
    chosen = []
    for label, keys in GALLERY_KEYWORDS.items():
        matches = [p for p in paths if any(x in p.stem.lower() for x in keys)]
        if matches:
            candidate = min(matches, key=lambda p: (len(p.parts), len(p.name)))
            if candidate not in [p for _, p in chosen]:
                chosen.append((label, candidate))
    return [(label, p.relative_to(repo).as_posix()) for label, p in chosen]


def discover_guardrails(frame: pd.DataFrame) -> tuple[tuple[str, str], ...]:
    candidates = []
    if "active_week_4" in frame.columns:
        candidates.append(("active_week_4", "increase"))
    for col in frame.columns:
        name = col.lower()
        if (
            "support" in name
            and ("14" in name or "d14" in name)
            and ("contact" in name or "ticket" in name)
        ):
            candidates.append((col, "decrease"))
    return tuple(candidates)


def build_readme(
    repo: Path,
    report: dict,
    images: list[tuple[str, str]],
    chart_names: list[str],
    observed_users: int,
    events_count: int | None,
    *,
    real_data_note: bool,
) -> str:
    p = report["primary"]
    s = report["srm"]
    metric_label = f"{p['absolute_lift'] * 100:+.2f} pp"
    ga4 = (
        (
            "### Separate public-data analysis\n\n"
            "The repository also includes `sql/bigquery_ga4_funnel.sql`, executed against Google's public, obfuscated GA4 ecommerce sample. "
            "This real-data SQL case study is distinct from the simulated subscription experiment.\n\n"
        )
        if real_data_note
        else ""
    )
    lines = [
        "# Product Experimentation & Customer Analytics",
        "",
        "**A product analytics and experimentation platform combining A/B test inference, behavioral funnels, cohort retention, predictive modeling, and executive reporting.**",
        "",
        "**Stack:** Python · SQL · DuckDB · SciPy · scikit-learn · BigQuery · Power BI · GitHub Actions",
        "",
        "> **Data scope:** The subscription experiment uses reproducible synthetic data, not real users or actual company performance. The public GA4 BigQuery extension is a separate dataset.",
        "",
        "## Project highlights",
        "",
        "| Experiment scale | Conversion lift | Experiment validation | Reporting |",
        "|---|---|---|---|",
        f"| **{observed_users:,} simulated users** | **{metric_label}** | **SRM p = {s['p_value']:.4g}** | **4-page Power BI report** |",
        "",
        f"For this seeded synthetic run, conversion increased from **{p['control_rate']:.2%} (control)** to **{p['treatment_rate']:.2%} (treatment)**. The estimated absolute lift was **{metric_label}** "
        f"(approximate 95% CI: **{p['ci_low'] * 100:+.2f} to {p['ci_high'] * 100:+.2f} percentage points**, two-sided p = **{p['p_value']:.3g}**).",
        "",
        "## Experiment and analytics showcase",
        "",
        "### Experiment outcome",
        "",
        "![Simulated treatment and control conversion comparison](docs/images/showcase_conversion.png)",
        "",
        "### Treatment effect and guardrails",
        "",
        "![Experiment effect sizes and confidence intervals](docs/images/showcase_effects.png)",
        "",
    ]
    if "showcase_channel.png" in chart_names:
        lines += [
            "### Acquisition-channel performance",
            "",
            "![Simulated channel conversion performance](docs/images/showcase_channel.png)",
            "",
        ]
    if "showcase_retention.png" in chart_names:
        lines += [
            "### Retention guardrail",
            "",
            "![Simulated week-four active-user rates](docs/images/showcase_retention.png)",
            "",
        ]
    if "showcase_subgroups.png" in chart_names:
        lines += [
            "### Exploratory segment effects",
            "",
            "![Treatment-effect estimates across simulated customer segments](docs/images/showcase_subgroups.png)",
            "",
            "Segment estimates are exploratory, and multiplicity-adjusted p-values are provided in the aggregate evidence.",
            "",
        ]
    if images:
        lines += [
            "## Power BI dashboard gallery",
            "",
            "The four-page report connects acquisition funnels, randomized experiment outcomes, retention cohorts, model evaluation, and quality checks.",
            "",
        ]
        for label, path in images:
            lines += [f"### {label}", "", f"![{label}]({path})", ""]
    else:
        lines += [
            "## Power BI reporting",
            "",
            "The existing four-page Power BI report covers executive metrics, the conversion funnel, cohort retention, and model/data quality. See [Power BI documentation](docs/power_bi.md).",
            "",
        ]
    guardrails = report["guardrails"]
    guardrail_desc = (
        (" and ".join(g["label"] for g in guardrails))
        if guardrails
        else "configured guardrails (if available)"
    )
    lines += [
        "## Engineering and analytical work",
        "",
        "| Workstream | Delivered capability |",
        "|---|---|",
        "| Data modeling | Seeded user assignments and event-level behavior with user-grain analytical outputs |",
        "| Product analytics | Funnel abandonment, customer cohorts, acquisition segments, and conversion reporting |",
        f"| Experimentation | Two-proportion inference, effect-size confidence intervals, sample-ratio checks, {guardrail_desc}, and power planning |",
        "| Predictive analytics | Chronologically evaluated week-four activity model with explicit outcome timing |",
        "| Reporting | Power BI report plus committed portfolio graphics derived from aggregate metrics |",
        "| Quality engineering | Automated tests, user-grain validation, no silent deduplication, and CI |",
        "",
        "## Experiment decision context",
        "",
        f"**Analytical classification:** `{report['decision']}`. The treatment has an estimated lift of **{metric_label}** relative to control on synthetic outcomes. "
        "This is a simulated analytical case study, not evidence of realized revenue, causal business impact at a company, or a completed live rollout.",
        "",
        "The SRM test evaluates arm allocation. A nonsignificant guardrail result does **not** establish equivalence or prove the absence of harm. "
        "For deployment, longer observation windows, instrumentation audits, and commercially relevant constraints would remain necessary.",
        "",
        "## Architecture",
        "",
        "```mermaid",
        "flowchart LR",
        "  A[Seeded simulation] --> B[User and event tables]",
        "  B --> C[DuckDB and SQL]",
        "  C --> D[Funnel and cohort analytics]",
        "  B --> E[Experiment and power analysis]",
        "  B --> F[Time-aware retention model]",
        "  D --> G[Power BI and portfolio evidence]",
        "  E --> G",
        "  F --> G",
        "```",
        "",
        ga4,
        "## Technical evidence",
        "",
        "- [Experiment validity and decision report](docs/EXPERIMENT_VALIDITY_METHOD.md)",
        "- [Seeded-run aggregate evidence](docs/evidence/showcase/experiment_validity.json)",
        "- [Exploratory subgroup estimates with Holm correction](docs/evidence/showcase/segment_effects.json)",
        "- [Retention model card](docs/RETENTION_MODEL_CARD_SHOWCASE.md)",
        "- [Existing architecture and data grains](docs/architecture.md)",
        "- [Existing data dictionary](docs/data_dictionary.md)",
        "- [Existing decision memo](docs/decision_memo.md)",
        "- [Power BI documentation](docs/power_bi.md)",
        "",
        "<details><summary>Reproducibility and local validation</summary>",
        "",
        "```powershell",
        "python -m pip install -r requirements.txt",
        "python -m pip install -r requirements-showcase.txt",
        "python -m src.pipeline --users 20000 --days 180 --seed 42",
        "python -m product_showcase.build --repo .",
        "python -m pytest -q",
        "```",
        "",
        "Generated user-level records and local databases are excluded from Git; published evidence contains aggregate results and screenshots.",
        "",
        "</details>",
        "",
        "## Author",
        "",
        "**Rishi Ratnakar** · [LinkedIn](https://www.linkedin.com/in/rishi-ratnakar/) · [GitHub](https://github.com/RishiRatnakarData)",
        "",
    ]
    return "\n".join(lines)


def write_retention_card(repo: Path) -> None:
    path = repo / "artifacts/retention_model_metrics.json"
    dest = repo / "docs/RETENTION_MODEL_CARD_SHOWCASE.md"
    if not path.is_file():
        dest.write_text(
            "# Retention model | Portfolio evidence\n\nNo model metrics file was generated in this run. See the source evaluation pipeline.\n",
            encoding="utf-8",
        )
        return
    metrics = json.loads(path.read_text(encoding="utf-8"))
    report = [
        "# Retention model | Evaluation summary",
        "",
        "> Synthetic week-four user activity; not a production churn or intervention model.",
        "",
        "| Holdout metric | Value |",
        "|---|---:|",
    ]
    for key, label in [
        ("train_rows", "Training rows"),
        ("test_rows", "Holdout rows"),
        ("roc_auc", "ROC-AUC"),
        ("average_precision", "Average precision"),
        ("precision", "Precision"),
        ("recall", "Recall"),
        ("f1", "F1"),
        ("threshold", "Classification threshold"),
    ]:
        if key in metrics:
            v = metrics[key]
            report.append(
                f"| {label} | {v:.4f} |"
                if isinstance(v, float)
                else f"| {label} | {v} |"
            )
    report += [
        "",
        "Model discrimination does not establish intervention benefit. Evaluation is scoped to the documented feature availability and holdout protocol.",
        "",
    ]
    dest.write_text("\n".join(report), encoding="utf-8")


def build(repo: Path, *, require_users: int = 20000) -> dict:
    repo = repo.resolve()
    outcomes_path = repo / "data/generated/experiment_outcomes.parquet"
    users_path = repo / "data/generated/users.parquet"
    if not outcomes_path.is_file() or not users_path.is_file():
        raise ValueError(
            "Missing generated Parquet. Run the existing full pipeline (20,000 users) before showcase generation."
        )
    outcomes = pd.read_parquet(outcomes_path)
    users = pd.read_parquet(users_path)
    if len(outcomes) != require_users or len(users) != require_users:
        raise ValueError(
            f"Expected {require_users:,} users/outcomes; found {len(users):,}/{len(outcomes):,}. Regenerate the full seeded pipeline first."
        )
    if (
        "user_id" not in users.columns
        or users.user_id.duplicated().any()
        or not users.user_id.isin(outcomes.user_id).all()
    ):
        raise ValueError(
            "User table does not reconcile one-to-one with experiment assignment table"
        )
    g = discover_guardrails(outcomes)
    report = analyze(outcomes, guardrails=g, practical_lift=0.01, srm_threshold=0.001)
    data_dir = repo / "docs/evidence/showcase"
    imgs = repo / "docs/images"
    imgs.mkdir(parents=True, exist_ok=True)
    write_outputs(report, data_dir)
    save_effect_plot(report, imgs / "showcase_effects.png")
    conversion_chart(report, imgs / "showcase_conversion.png")
    charts = ["showcase_effects.png", "showcase_conversion.png"]
    if channel_chart(users, outcomes, imgs / "showcase_channel.png"):
        charts.append("showcase_channel.png")
    if retention_chart(outcomes, imgs / "showcase_retention.png"):
        charts.append("showcase_retention.png")
    effects = segment_effects(users, outcomes)
    (data_dir / "segment_effects.json").write_text(
        json.dumps(
            {
                "scope": "exploratory synthetic subgroups",
                "method": "unpooled Wald interval; pooled z-test; Holm multiple-testing correction",
                "effects": effects,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if subgroup_chart(effects, imgs / "showcase_subgroups.png"):
        charts.append("showcase_subgroups.png")
    write_retention_card(repo)
    # Importantly, do not copy the entire generated dataset or holdout predictions into Git.
    evt_path = repo / "data/generated/events.parquet"
    evt_count = (
        len(pd.read_parquet(evt_path, columns=["user_id"]))
        if evt_path.is_file()
        else None
    )
    image_list = find_dashboard_images(repo)
    original = (repo / "README.md").read_text(encoding="utf-8")
    real_data_note = (
        "bigquery_ga4_funnel.sql" in original.lower()
        or (repo / "sql/bigquery_ga4_funnel.sql").exists()
    )
    content = build_readme(
        repo,
        report,
        image_list,
        charts,
        len(users),
        evt_count,
        real_data_note=real_data_note,
    )
    (repo / "README.md").write_text(content, encoding="utf-8", newline="\n")
    manifest = {
        "scope": "seeded synthetic subscription experiment",
        "users": len(users),
        "events": evt_count,
        "generated_chart_paths": ["docs/images/" + c for c in charts],
        "gallery": [x for x, _ in image_list],
        "primary_absolute_lift": report["primary"]["absolute_lift"],
        "primary_p_value": report["primary"]["p_value"],
        "guardrail_columns": [x["column"] for x in report["guardrails"]],
        "exploratory_subgroups": len(effects),
        "srm_flag": report["srm"]["flagged"],
        "decision": report["decision"],
        "note": "Not evidence of live product impact; aggregated result from deterministic simulation.",
    }
    (data_dir / "showcase_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--users", type=int, default=20000)
    args = p.parse_args()
    print(json.dumps(build(args.repo, require_users=args.users), indent=2))


if __name__ == "__main__":
    main()
