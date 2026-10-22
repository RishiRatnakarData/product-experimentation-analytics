"""Recruiter-first README presentation shared by the Product Experimentation generator.

Keep aggregate analytical output separate from presentation. Existing dashboard screenshots
are linked only when the caller has verified their presence on disk.
"""

from __future__ import annotations

from pathlib import Path


def _gallery(items: list[tuple[str, str]], columns: int = 2) -> list[str]:
    """Compact linked screenshots rather than a sequence of full-width images."""
    lines: list[str] = []
    for start in range(0, len(items), columns):
        group = items[start : start + columns]
        lines.append("| " + " | ".join(label for label, _ in group) + " |")
        lines.append("| " + " | ".join(":---:" for _ in group) + " |")
        cells = []
        for label, path in group:
            cells.append(f"[![{label}]({path})]({path})")
        lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return lines


def retention_summary(metrics: dict | None) -> str:
    """Describe the actual evaluated holdout; never infer model quality from row count."""
    if metrics is None:
        return (
            "Retention evaluation metrics are not available for this run. "
            "See the model card for the evaluation protocol."
        )
    import math

    values = []
    for key in ("roc_auc", "average_precision"):
        value = metrics.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Retention metric {key} must be numeric")
        if not math.isfinite(float(value)) or not 0 <= float(value) <= 1:
            raise ValueError(f"Retention metric {key} must be finite and in [0, 1]")
        values.append(float(value))
    holdout = metrics.get("test_rows")
    if isinstance(holdout, bool) or not isinstance(holdout, int) or holdout <= 0:
        raise ValueError("Retention model test_rows must be a positive integer")
    return (
        f"The chronological retention-model holdout (n = {holdout:,}) achieved "
        f"**{values[0]:.3f} ROC-AUC** and **{values[1]:.3f} average precision** "
        "on simulated outcomes. These scores measure prediction, not the "
        "impact of an intervention."
    )


def build_readme(
    repo: Path | None,
    report: dict,
    images: list[tuple[str, str]],
    chart_names: list[str],
    observed_users: int,
    events_count: int | None,
    *,
    real_data_note: bool,
    retention_metrics: dict | None = None,
) -> str:
    """Create concise, gallery-first output using only measured synthetic-run results."""
    primary = report["primary"]
    srm = report["srm"]
    lift = f"{primary['absolute_lift'] * 100:+.2f}"
    n_events = f"{events_count:,}" if events_count is not None else "Not recorded"
    lines = [
        "# Product Experimentation & Customer Analytics",
        "",
        "**An end-to-end product analytics project combining randomized-experiment evaluation, SQL funnels, retention modeling, and executive reporting.**",
        "",
        "**Python · SQL · DuckDB · SciPy · scikit-learn · BigQuery · Power BI · GitHub Actions**",
        "",
    ]
    hero = images[0][1] if images else "docs/images/showcase_conversion.png"
    lines.extend(
        [
            f"![Product analytics reporting overview]({hero})",
            "",
            "[**Dashboard gallery**](#dashboard-gallery) · [**Results**](#selected-results) · "
            "[**Experiment evidence**](#experiment-and-retention-evidence) · "
            "[**Architecture**](#solution-architecture) · "
            "[**Technical evidence**](#technical-evidence)",
            "",
            "## Project overview",
            "",
            "A subscription-product analytics case study spanning acquisition, conversion, and customer retention. "
            "The system models user-level experiment assignments and behavioral events, builds funnel and cohort views in DuckDB, "
            "evaluates treatment effects and guardrails, and reports retention-model performance.",
            "",
            "**Data scope:** The controlled experiment uses reproducible **synthetic data**, not real users or observed company results. "
            "The separate public GA4 analysis, where included, uses an independent obfuscated ecommerce dataset.",
            "",
            "## Selected results",
            "",
            "| Area | Verified simulated-run result | Evidence |",
            "|---|---|---|",
            f"| Experiment scale | **{observed_users:,} simulated users**; {n_events} generated events | [Aggregate results](docs/evidence/showcase/experiment_validity.json) |",
            f"| Conversion | **{primary['control_rate']:.2%} → {primary['treatment_rate']:.2%}** (control → treatment) | [Experiment decision memo](docs/evidence/showcase/experiment_validity_memo.md) |",
            f"| Treatment effect | **{lift} percentage points**, approximate 95% CI **[{primary['ci_low'] * 100:+.2f}, {primary['ci_high'] * 100:+.2f}]**; p = **{primary['p_value']:.3g}** | [Methods](docs/EXPERIMENT_VALIDITY_METHOD.md) |",
            f"| Allocation quality | SRM p = **{srm['p_value']:.4f}**; {'flagged' if srm['flagged'] else 'not flagged'} | [Aggregate results](docs/evidence/showcase/experiment_validity.json) |",
            "| Reporting | Four-page Power BI report and validated user-grain SQL views | [Power BI measures](docs/power_bi.md) |",
            "",
            "The experiment's treatment effect is embedded in a deterministic simulation; its measured lift "
            "demonstrates analytical implementation rather than live business impact.",
            "",
            "## Dashboard gallery",
            "",
            "The reporting layer brings the experiment, acquisition funnel, customer cohorts, and model/data quality into one Power BI experience.",
            "",
        ]
    )
    if images:
        lines.extend(_gallery(images, columns=2))
    else:
        lines += [
            "Dashboard screenshots were not found in this checkout; the four-page report is documented in "
            "[Power BI design and measures](docs/power_bi.md).",
            "",
        ]
    lines.extend(
        [
            "## Experiment and retention evidence",
            "",
            "**Experiment outcome and uncertainty.** The primary treatment effect was evaluated using user-level assignments "
            "and an independent control-versus-treatment comparison. Guardrails and sample-ratio checks accompany the result.",
            "",
            "| Conversion by assignment | Effect estimates and guardrails |",
            "|:---:|:---:|",
            "| [![Simulated treatment and control conversion comparison](docs/images/showcase_conversion.png)](docs/images/showcase_conversion.png) | [![Treatment effect and guardrail intervals](docs/images/showcase_effects.png)](docs/images/showcase_effects.png) |",
            "",
            retention_summary(retention_metrics),
            "",
            "<details>",
            "<summary><strong>Additional analysis: channels, retention and segments</strong></summary>",
            "",
        ]
    )
    additional = [
        ("Acquisition channels", "docs/images/showcase_channel.png"),
        ("Week-4 activity", "docs/images/showcase_retention.png"),
        ("Exploratory segments", "docs/images/showcase_subgroups.png"),
    ]
    present = [
        (label, path) for label, path in additional if Path(path).name in chart_names
    ]
    if present:
        lines.extend(_gallery(present, columns=2))
    lines.extend(
        [
            "Exploratory subgroup estimates are not independent confirmatory findings; "
            "their Holm-adjusted p-values are retained in the supporting evidence.",
            "",
            "</details>",
            "",
            "## Solution architecture",
            "",
            "```mermaid",
            "flowchart LR",
            "    A[Seeded assignments and events] --> B[Validated user and event tables]",
            "    B --> C[DuckDB and SQL marts]",
            "    C --> D[Funnel and cohort reports]",
            "    B --> E[Experiment analysis and guardrails]",
            "    B --> F[Time-aware retention model]",
            "    D --> G[Power BI]",
            "    E --> G",
            "    F --> G",
            "```",
            "",
            "**Engineering highlights**",
            "",
            "- **Event and user modeling:** separate event-grain observations from unique assignment and outcome records.",
            "- **Experiment validity:** allocation checks, proportion inference, confidence intervals, practical-effect criteria, and guardrails.",
            "- **Retention prediction:** chronological holdout and features available before the predicted observation window.",
            "- **Business intelligence:** funnel abandonment, cohort retention, acquisition-channel comparisons, and model/quality reporting.",
            "- **Quality:** deterministic generation, automated tests, code linting, and user-grain integrity checks.",
            "",
        ]
    )
    if real_data_note:
        lines += [
            "## Separate public-data analysis",
            "",
            "A BigQuery funnel analysis using Google's public, obfuscated GA4 ecommerce sample is included "
            "in [`sql/bigquery_ga4_funnel.sql`](sql/bigquery_ga4_funnel.sql). This is a separate dataset from the synthetic subscription experiment.",
            "",
        ]
    lines += [
        "## Repository map",
        "",
        "| Location | Contents |",
        "|---|---|",
        "| [`src/`](src/) and [`sql/`](sql/) | Data generation, model logic, DuckDB analytical views, BigQuery query |",
        "| [`experiment_validity/`](experiment_validity/) | User-grain experiment diagnostics and uncertainty reporting |",
        "| [`product_showcase/`](product_showcase/) | Aggregate evidence, analytics visuals, README generation |",
        "| [`docs/`](docs/) | Architecture, Power BI notes, model card, and case-study evidence |",
        "| [`tests/`](tests/), [`tests_experiment_validity/`](tests_experiment_validity/), [`tests_showcase/`](tests_showcase/) | Automated analytical and presentation checks |",
        "",
        "## Technical evidence",
        "",
        "[Experiment decision report](docs/evidence/showcase/experiment_validity_memo.md) · "
        "[Aggregate experiment results](docs/evidence/showcase/experiment_validity.json) · "
        "[Exploratory segments](docs/evidence/showcase/segment_effects.json) · "
        "[Retention model card](docs/RETENTION_MODEL_CARD_SHOWCASE.md) · "
        "[Architecture](docs/architecture.md) · "
        "[Power BI design](docs/power_bi.md)",
        "",
        "<details>",
        "<summary><strong>Reproducibility and local validation</strong></summary>",
        "",
        "```powershell",
        "python -m pip install -r requirements.txt",
        "python -m pip install -r requirements-showcase.txt",
        "python -m src.pipeline --users 20000 --days 180 --seed 42",
        "python -m product_showcase.build --repo .",
        "python -m pytest -q",
        "```",
        "",
        "Generated user-level datasets and local databases are not committed. The published charts are derived from aggregate simulation evidence.",
        "",
        "</details>",
        "",
        "## Data and interpretation",
        "",
        "The treatment comparison is retrospective analysis of simulated outcomes, not a company A/B test "
        "or an observed causal business result. Nonsignificant guardrails do not establish equivalence. "
        "Real rollout decisions would require instrumentation verification, operational cost, and longitudinal evidence.",
        "",
        "---",
        "",
        "**Rishi Ratnakar** · [GitHub](https://github.com/RishiRatnakarData) · "
        "[LinkedIn](https://www.linkedin.com/in/rishi-ratnakar/)",
        "",
    ]
    return "\n".join(lines)
