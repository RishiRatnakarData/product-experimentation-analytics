"""CUPED diagnostics on seeded fictional randomized users."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from experiment_validity.cuped import analyze_cuped
from scripts.make_cuped_fixture import create_fixture


@pytest.fixture
def fixture(tmp_path):
    return create_fixture(tmp_path / "cuped_users.csv")


def test_known_within_arm_theta_and_treatment_adjustment():
    frame = pd.DataFrame({
        "user_id": list(range(1, 9)) * 5,
        "variant": ["control"] * 20 + ["treatment"] * 20,
        "pre_period_engagement_score": [0, 1, 2, 3] * 10,
        "converted": [0, 0, 1, 1] * 10,
    })
    frame["user_id"] = range(40)
    result = analyze_cuped(frame)
    # Covariance numerator within each arm = 2; denominator = 5 per 4 rows.
    assert result["theta_within_arm"] == pytest.approx(0.4)
    assert result["cuped_adjusted"]["effect"] == pytest.approx(0)
    assert result["measured_variance_reduction_fraction"] > 0


def test_seeded_fixture_is_reproducible_and_measures_variance_reduction(fixture, tmp_path):
    report = analyze_cuped(fixture)
    second = create_fixture(tmp_path / "other.csv")
    pd.testing.assert_frame_equal(fixture, second)
    assert report == analyze_cuped(fixture.copy(deep=True))
    assert report["original"]["control_n"] + report["original"]["treatment_n"] == 3000
    assert report["cuped_adjusted"]["standard_error"] < report["original"]["standard_error"]
    assert report["measured_variance_reduction_fraction"] > 0
    assert report["original"]["ci_low"] <= report["original"]["effect"] <= report["original"]["ci_high"]


def test_does_not_use_post_treatment_guardrail(fixture):
    fixture["active_week_4"] = 1
    with pytest.raises(ValueError, match="pre-treatment"):
        analyze_cuped(fixture, covariate="active_week_4")


def test_does_not_accept_duplicate_or_missing_users(fixture):
    frame = fixture.copy()
    frame.loc[1, "user_id"] = frame.loc[0, "user_id"]
    with pytest.raises(ValueError, match="one unique"):
        analyze_cuped(frame)
    frame = fixture.copy()
    frame.loc[1, "user_id"] = np.nan
    with pytest.raises(ValueError, match="one unique"):
        analyze_cuped(frame)


def test_missing_invalid_covariate_values_fail(fixture):
    frame = fixture.copy()
    frame.loc[1, "pre_period_engagement_score"] = np.nan
    with pytest.raises(ValueError, match="complete and finite"):
        analyze_cuped(frame)
    frame = fixture.copy()
    frame.loc[1, "pre_period_engagement_score"] = np.inf
    with pytest.raises(ValueError, match="complete and finite"):
        analyze_cuped(frame)


def test_missing_and_invalid_outcome_values_fail(fixture):
    frame = fixture.copy()
    frame.loc[1, "converted"] = 2
    with pytest.raises(ValueError, match="0 or 1"):
        analyze_cuped(frame)
    frame.loc[1, "converted"] = np.nan
    with pytest.raises(ValueError, match="0 or 1"):
        analyze_cuped(frame)


def test_missing_column_and_invalid_groups_fail(fixture):
    with pytest.raises(ValueError, match="Missing required"):
        analyze_cuped(fixture.drop(columns="pre_period_engagement_score"))
    frame = fixture.copy()
    frame.loc[0, "variant"] = "other"
    with pytest.raises(ValueError, match="exactly control"):
        analyze_cuped(frame)
    with pytest.raises(ValueError, match="at least 10"):
        analyze_cuped(fixture.iloc[:15])


def test_zero_covariate_variation_fails(fixture):
    frame = fixture.copy()
    frame["pre_period_engagement_score"] = 0
    with pytest.raises(ValueError, match="vary"):
        analyze_cuped(frame)


def test_no_automatic_significance_claim(fixture):
    report = analyze_cuped(fixture)
    assert "significant" not in report["interpretation"].casefold()
    assert any("No significance" in item for item in report["caveats"])


def test_cli_output_is_valid_json(fixture, monkeypatch, tmp_path):
    import sys
    from scripts import run_cuped

    data = tmp_path / "test.csv"
    out = tmp_path / "report.json"
    fixture.to_csv(data, index=False)
    monkeypatch.setattr(sys, "argv", ["run_cuped", "--data", str(data), "--out", str(out)])
    run_cuped.main()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["analysis_type"] == "synthetic_user_level_cuped_demonstration"
    assert report["original"]["standard_error"] > 0
    assert "user_id" not in report
