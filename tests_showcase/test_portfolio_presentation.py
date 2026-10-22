"""Regression tests for the recruiter-first product analytics README."""

from __future__ import annotations

from experiment_validity.analysis import analyze
from product_showcase.presentation import build_readme
import pandas as pd


def _report() -> dict:
    sample = pd.DataFrame(
        {
            "user_id": list(range(20)),
            "variant": ["control"] * 10 + ["treatment"] * 10,
            "converted": [0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 1],
        }
    )
    return analyze(sample)


def test_dashboard_gallery_precedes_experiment_charts() -> None:
    doc = build_readme(None, _report(), [("Executive overview", "docs/images/executive.png")], ["showcase_conversion.png"], 20, 100, real_data_note=False)
    assert doc.index("## Dashboard gallery") < doc.index("## Experiment and retention evidence")
    assert "![Executive overview]" in doc
    assert "20 simulated users" in doc


def test_secondary_charts_are_collapsed() -> None:
    doc = build_readme(None, _report(), [], ["showcase_subgroups.png"], 20, 100, real_data_note=True)
    assert "<details>" in doc
    assert "showcase_subgroups.png" in doc
    assert "not real users" in doc
    assert "GA4" in doc


def test_intro_not_a_tutorial() -> None:
    doc = build_readme(None, _report(), [], [], 20, None, real_data_note=False)
    assert doc.startswith("# Product Experimentation & Customer Analytics")
    assert "## Selected results" in doc
    assert "## Solution architecture" in doc
    assert "not real users" in doc
