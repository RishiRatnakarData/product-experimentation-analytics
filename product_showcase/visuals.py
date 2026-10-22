"""Static visuals for a simulated experiment portfolio, with no individual-level exports."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd

INK = "#172b4d"
TEAL = "#007f86"
PURPLE = "#6554a4"
matplotlib.use("Agg")

MUTED = "#60748d"
BG = "#fafbfc"


def _canvas(w: float = 9, h: float = 4.8):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=INK)
    return fig, ax


def conversion_chart(report: dict, path: Path) -> None:
    m = report["primary"]
    fig, ax = _canvas(9, 5.0)
    means = [m["control_rate"], m["treatment_rate"]]
    ax.bar(["Control", "Treatment"], means, color=[MUTED, TEAL], width=0.5)
    for i, v in enumerate(means):
        ax.text(
            i, v + 0.005, f"{v:.2%}", ha="center", weight="bold", color=INK, fontsize=14
        )
    ax.set_ylim(0, max(means) * 1.34)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Subscription conversion rate")
    ax.set_title(
        "Conversion outcome | Simulated A/B experiment",
        color=INK,
        fontsize=16,
        pad=18,
        weight="bold",
    )
    ax.text(
        0.5,
        1.01,
        f"Treatment lift: {m['absolute_lift'] * 100:+.2f} pp  |  95% CI: [{m['ci_low'] * 100:+.2f}, {m['ci_high'] * 100:+.2f}] pp",
        transform=ax.transAxes,
        ha="center",
        color=INK,
    )
    fig.text(
        0.02,
        0.015,
        "Simulated subscription product; confidence interval is an unpooled normal approximation",
        fontsize=9,
        color=MUTED,
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def channel_chart(users: pd.DataFrame, outcomes: pd.DataFrame, path: Path) -> bool:
    if not {"user_id", "channel"}.issubset(users.columns):
        return False
    if not {"user_id", "converted"}.issubset(outcomes.columns):
        return False
    if users.user_id.duplicated().any() or outcomes.user_id.duplicated().any():
        return False
    f = users[["user_id", "channel"]].merge(
        outcomes[["user_id", "converted"]], on="user_id", validate="one_to_one"
    )
    if len(f) != len(outcomes) or f["channel"].isna().any():
        return False
    summary = (
        f.groupby("channel")["converted"]
        .agg(["mean", "count"])
        .sort_values("mean", ascending=True)
    )
    fig, ax = _canvas(9, 4.7)
    ax.barh(summary.index.astype(str), summary["mean"], color=TEAL, height=0.64)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlim(0, max(0.05, summary["mean"].max() * 1.22))
    for i, (v, n) in enumerate(zip(summary["mean"], summary["count"])):
        ax.text(v + 0.003, i, f"{v:.1%}  ·  n={n:,}", va="center", color=INK)
    ax.set_xlabel("Simulated conversion rate")
    ax.set_title(
        "Conversion by acquisition channel",
        color=INK,
        fontsize=16,
        pad=18,
        weight="bold",
    )
    fig.text(
        0.02,
        0.01,
        "Descriptive segments; randomized experiment effect is not estimated by this chart",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return True


def retention_chart(outcomes: pd.DataFrame, path: Path) -> bool:
    needed = {"variant", "active_week_4"}
    if not needed.issubset(outcomes.columns):
        return False
    d = (
        outcomes.groupby("variant")["active_week_4"]
        .agg(["count", "mean"])
        .reindex(["control", "treatment"])
    )
    if d.isna().any().any():
        return False
    fig, ax = _canvas(9, 4.5)
    ax.bar(d.index, [float(x) for x in d["mean"]], color=[MUTED, PURPLE], width=0.5)
    for i, (_, r) in enumerate(d.iterrows()):
        ax.text(
            i,
            float(r["mean"]) + 0.005,
            f"{r['mean']:.2%}",
            ha="center",
            fontsize=13,
            weight="bold",
            color=INK,
        )
    ax.set_ylim(0, max(0.05, float(d["mean"].max()) * 1.32))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Week-4 active-user rate")
    ax.set_title(
        "Week-4 activity | Experiment guardrail",
        color=INK,
        fontsize=16,
        pad=18,
        weight="bold",
    )
    fig.text(
        0.02,
        0.01,
        "Synthetic outcomes; week-4 activity measured only for defined simulated windows",
        color=MUTED,
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return True


def subgroup_chart(effects: list[dict], path: Path) -> bool:
    if not effects:
        return False
    displayed = sorted(effects, key=lambda e: (e["dimension"], e["segment"]))[:16]
    fig, ax = _canvas(11, max(4, 1.5 + 0.43 * len(displayed)))
    for i, item in enumerate(displayed):
        eff = item["absolute_lift"] * 100
        lo = item["ci_low"] * 100
        hi = item["ci_high"] * 100
        ax.errorbar(
            eff, i, xerr=[[eff - lo], [hi - eff]], fmt="o", color=TEAL, capsize=3
        )
    ax.set_yticks(
        range(len(displayed)), [f"{x['dimension']}: {x['segment']}" for x in displayed]
    )
    ax.invert_yaxis()
    ax.axvline(0, ls="--", color=MUTED, alpha=0.6)
    ax.set_xlabel("Exploratory treatment − control conversion lift (percentage points)")
    ax.set_title(
        "Segment effect diagnostics | Synthetic experiment",
        fontsize=16,
        pad=18,
        color=INK,
        weight="bold",
    )
    fig.text(
        0.02,
        0.005,
        "Approximate 95% intervals are unadjusted. Holm p-values stored in aggregate evidence; subgroup effects are exploratory.",
        fontsize=8.5,
        color=MUTED,
    )
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return True
