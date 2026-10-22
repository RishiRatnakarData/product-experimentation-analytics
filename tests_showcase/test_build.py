import pandas as pd
import pytest
from product_showcase.build import (
    build_readme,
    discover_guardrails,
    find_dashboard_images,
)
from experiment_validity.analysis import analyze


def frame():
    return pd.DataFrame(
        {
            "user_id": list(range(1, 9)),
            "variant": ["control"] * 4 + ["treatment"] * 4,
            "converted": [0, 0, 1, 0, 1, 1, 1, 0],
            "active_week_4": [1, 0, 0, 1, 1, 1, 1, 0],
            "support_contact_day_14": [0, 0, 1, 0, 1, 0, 0, 0],
        }
    )


def test_detect_guardrails():
    assert discover_guardrails(frame()) == (
        ("active_week_4", "increase"),
        ("support_contact_day_14", "decrease"),
    )


def test_missing_guardrails_are_not_invented():
    assert (
        discover_guardrails(
            frame().drop(columns=["active_week_4", "support_contact_day_14"])
        )
        == ()
    )


def test_showcase_discloses_synthetic_scope(tmp_path):
    report = analyze(frame(), guardrails=discover_guardrails(frame()))
    text = build_readme(tmp_path, report, [], [], 8, 25, real_data_note=False)
    assert "synthetic" in text.lower() and "not real users" in text.lower()
    assert "8 simulated users" in text
    assert "![Simulated treatment" in text
    assert "20,000" not in text


def test_ga4_disclosure_separate():
    report = analyze(frame())
    text = build_readme(None, report, [], [], 8, None, real_data_note=True)
    assert "separate dataset" in text.lower()
    assert "GA4" in text


def test_gallery_only_uses_existing_local_images(tmp_path):
    d = tmp_path / "docs/images"
    d.mkdir(parents=True)
    (d / "executive_overview.png").write_bytes(b"test")
    (d / "conversion_funnel.png").write_bytes(b"test")
    images = find_dashboard_images(tmp_path)
    assert len(images) == 2 and all(x[1].startswith("docs/images/") for x in images)


def test_strict_user_count_validation(tmp_path):
    with pytest.raises(ValueError, match="Missing generated"):
        from product_showcase.build import build

        build(tmp_path)


def test_exploratory_holm_adjustment():
    from product_showcase.segments import segment_effects

    users = pd.DataFrame({"user_id": range(100), "channel": ["a"] * 50 + ["b"] * 50})
    outcomes = pd.DataFrame(
        {
            "user_id": range(100),
            "variant": ["control", "treatment"] * 50,
            "converted": [0, 1] * 50,
        }
    )
    effects = segment_effects(users, outcomes, min_arm=12)
    assert len(effects) == 2
    assert all(x["holm_p_value"] >= x["p_value"] for x in effects)


def test_segment_grain_mismatch_rejected():
    from product_showcase.segments import segment_effects

    users = pd.DataFrame({"user_id": [1, 2, 3], "channel": ["a", "a", "a"]})
    outcomes = pd.DataFrame(
        {
            "user_id": [1, 2, 2],
            "variant": ["control", "treatment", "control"],
            "converted": [0, 1, 0],
        }
    )
    with pytest.raises(ValueError, match="unique"):
        segment_effects(users, outcomes)


def test_end_to_end_generates_only_aggregate_evidence(tmp_path, monkeypatch):
    import json
    import numpy as np
    from product_showcase.build import build

    rng = np.random.default_rng(17)
    n = 200
    users = pd.DataFrame(
        {
            "user_id": range(n),
            "channel": ["organic"] * 100 + ["paid_search"] * 100,
            "device": ["mobile"] * 100 + ["desktop"] * 100,
        }
    )
    outcomes = pd.DataFrame(
        {
            "user_id": range(n),
            "variant": ["control", "treatment"] * 100,
            "converted": (rng.random(n) < 0.24).astype(int),
            "active_week_4": (rng.random(n) < 0.4).astype(int),
        }
    )
    events = pd.DataFrame({"user_id": range(n)})
    directory = tmp_path / "data/generated"
    directory.mkdir(parents=True)
    for file in ["users.parquet", "experiment_outcomes.parquet", "events.parquet"]:
        (directory / file).write_bytes(b"stub")
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(
        "# Test\n\nBigQuery sql/bigquery_ga4_funnel.sql\n", encoding="utf-8"
    )
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/retention_model_metrics.json").write_text(
        json.dumps({"roc_auc": 0.64, "train_rows": 150, "test_rows": 50})
    )

    def read_stub(path, columns=None):
        fname = str(path)
        result = (
            users
            if fname.endswith("users.parquet")
            else outcomes
            if fname.endswith("experiment_outcomes.parquet")
            else events
        )
        return result[columns] if columns is not None else result

    monkeypatch.setattr(pd, "read_parquet", read_stub)
    result = build(tmp_path, require_users=n)
    assert result["users"] == n
    assert len(result["generated_chart_paths"]) >= 4
    assert (tmp_path / "docs/evidence/showcase/experiment_validity.json").exists()
    assert (tmp_path / "docs/RETENTION_MODEL_CARD_SHOWCASE.md").exists()
    assert "200 simulated users" in (tmp_path / "README.md").read_text()
    assert not list((tmp_path / "docs/evidence/showcase").glob("*.csv"))
