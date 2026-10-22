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


def build_readme(repo: Path, report: dict, images: list[tuple[str, str]], chart_names: list[str], observed_users: int, events_count: int | None, *, real_data_note: bool) -> str:
    """Return the consolidated dashboard-first portfolio presentation."""
    from .presentation import build_readme as render_portfolio_readme
    return render_portfolio_readme(repo, report, images, chart_names, observed_users, events_count, real_data_note=real_data_note)


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
