"""Regression tests: portfolio statistics must follow the current model run."""

import pytest

from product_showcase.presentation import retention_summary


def test_retention_readme_metrics_are_run_specific():
    first = retention_summary(
        {"test_rows": 4000, "roc_auc": 0.641024, "average_precision": 0.405761}
    )
    second = retention_summary(
        {"test_rows": 4200, "roc_auc": 0.7131, "average_precision": 0.5302}
    )
    assert "0.641 ROC-AUC" in first
    assert "0.406 average precision" in first
    assert "0.713 ROC-AUC" in second
    assert "0.530 average precision" in second
    assert "0.641" not in second
    assert "4,200" in second


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan")])
def test_invalid_scores_are_not_displayed(value):
    with pytest.raises(ValueError):
        retention_summary(
            {"test_rows": 100, "roc_auc": value, "average_precision": 0.5}
        )


def test_unavailable_metrics_never_reuse_a_previous_result():
    message = retention_summary(None)
    assert "not available" in message
    assert "0.641" not in message
