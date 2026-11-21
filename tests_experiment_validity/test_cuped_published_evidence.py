"""Verify checked-in CUPED aggregate results against seeded source code."""

import json
from pathlib import Path

import pytest

from experiment_validity.cuped import analyze_cuped
from scripts.make_cuped_fixture import create_fixture


def test_published_cuped_evidence_reproduces(tmp_path):
    path = Path(__file__).resolve().parents[1] / "docs/evidence/showcase/cuped_synthetic.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))
    assert evidence["analysis_type"] == "separate_seeded_synthetic_cuped_experiment"
    assert evidence["seed"] == 42
    assert evidence["users"] == 3000
    assert evidence["limitations"]
    result = analyze_cuped(create_fixture(tmp_path / "users.csv", users=3000, seed=42))
    assert evidence["control_users"] == result["original"]["control_n"]
    assert evidence["treatment_users"] == result["original"]["treatment_n"]
    for category in ("original", "cuped_adjusted"):
        for field in ("effect", "standard_error", "ci_low", "ci_high", "p_value"):
            assert evidence[category][field] == pytest.approx(result[category][field], abs=1e-9)
    assert evidence["measured_variance_reduction_fraction"] == pytest.approx(
        result["measured_variance_reduction_fraction"], abs=1e-9
    )
