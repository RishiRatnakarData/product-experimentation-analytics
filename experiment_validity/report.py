"""Static decision evidence for portfolio presentation, separate from Power BI."""
from __future__ import annotations

import json
from pathlib import Path


def _pct(value: float) -> str:
    return f"{100*value:.2f}%"


def _pp(value: float) -> str:
    return f"{100*value:+.2f} pp"


def write_outputs(report: dict, directory: str | Path) -> list[Path]:
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    jp=directory/"experiment_validity.json"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False),encoding="utf-8")
    primary=report["primary"]
    srm=report["srm"]
    decision=report["decision"].replace("_"," ").capitalize()
    mde=report["power_planning"]["mde_approx"]
    lines=[
        "# Experiment validity | Decision evidence",
        "",
        "**Scope:** Seeded synthetic subscription experiment; estimates do not represent observed commercial results.",
        "",
        f"**Review outcome:** {decision}",
        "",
        "## Primary outcome — subscription conversion",
        "",
        "| Measure | Verified from supplied user-level file |",
        "|---|---:|",
        f"| Control users | {primary['control_n']:,} |",
        f"| Treatment users | {primary['treatment_n']:,} |",
        f"| Control conversion | {_pct(primary['control_rate'])} |",
        f"| Treatment conversion | {_pct(primary['treatment_rate'])} |",
        f"| Absolute difference | {_pp(primary['absolute_lift'])} |",
        f"| Approximate 95% CI | [{_pp(primary['ci_low'])}, {_pp(primary['ci_high'])}] |",
        f"| Two-sided p-value | {primary['p_value']:.5g} |",
        f"| SRM p-value | {srm['p_value']:.5g} |",
        f"| SRM flagged | {'Yes' if srm['flagged'] else 'No'} |",
        f"| 80%-power MDE (equal-arm approximation) | {_pp(mde) if mde is not None else 'Not estimable'} |",
        "",
        "## Guardrails",
        "",
    ]
    if report["guardrails"]:
        lines.extend(["| Guardrail | Control | Treatment | Difference | Approximate 95% CI | Significant adverse direction? |","|---|---:|---:|---:|---|---|"])
        for g in report["guardrails"]:
            lines.append(f"| {g['label']} | {_pct(g['control_rate'])} | {_pct(g['treatment_rate'])} | {_pp(g['absolute_lift'])} | [{_pp(g['ci_low'])}, {_pp(g['ci_high'])}] | {'Yes' if g['significant_harm'] else 'No'} |")
    else:
        lines.append("No guardrail fields were specified in this execution. Do not infer that guardrails passed.")
    lines.extend(["", "## Decision interpretation", "", "This is research evidence from simulated outcomes. `Candidate for monitored review` is not an automated shipment or causal business-value recommendation.", "", "## Boundaries", ""])
    lines.extend(f"- {x}" for x in report["caveats"])
    lines.append("")
    md=directory/"experiment_validity_memo.md"
    md.write_text("\n".join(lines),encoding="utf-8")
    return [jp,md]


def save_effect_plot(report: dict, output: str | Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    metrics=[report["primary"], *report["guardrails"]]
    fig,ax=plt.subplots(figsize=(10, max(3.6, 1.1+len(metrics)*1.15)))
    for idx,m in enumerate(metrics):
        x=m["absolute_lift"]*100
        ax.errorbar(x,idx,xerr=[[100*(m["absolute_lift"]-m["ci_low"])],[100*(m["ci_high"]-m["absolute_lift"])]],fmt="o",capsize=4)
    ax.axvline(0,linestyle="--",alpha=.5)
    ax.set_yticks(range(len(metrics)),[m["label"] for m in metrics])
    ax.set_ylim(len(metrics)-.4,-.65)
    ax.set_xlabel("Treatment − control (percentage points; approximate 95% CI)")
    ax.set_title("Simulated experiment | User-level effect estimates",fontweight="bold")
    fig.text(.02,.01,"Synthetic observations • CI uses unpooled normal approximation • Not real business impact",fontsize=8)
    fig.tight_layout(rect=[0,.04,1,1])
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=170)
    plt.close(fig)
    return output
